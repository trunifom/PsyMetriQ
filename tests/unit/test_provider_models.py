import asyncio
from typing import Any

import pytest

from src.ingestion.provider_models import ModelDiscoveryError, list_available_models


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("GET", "https://provider.example/v1/models")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("provider error", request=request, response=response)

    def json(self) -> Any:
        return self.payload


class FakeHTTPClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.request: tuple[str, dict[str, Any]] | None = None

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.request = (url, kwargs)
        return self.response


@pytest.mark.parametrize(
    ("provider", "base_url", "payload", "expected"),
    [
        (
            "openai",
            None,
            {"data": [{"id": "gpt-z"}, {"id": "gpt-a"}]},
            ["gpt-a", "gpt-z"],
        ),
        (
            "alpineai",
            None,
            {"data": ["llama-4", "mistral-large"]},
            ["llama-4", "mistral-large"],
        ),
        (
            "openai-compatible",
            "https://llm.example/v1/",
            {"data": [{"id": "model-b"}, {"id": "model-b"}, {"id": "model-a"}]},
            ["model-a", "model-b"],
        ),
    ],
)
def test_openai_compatible_providers_parse_available_model_ids(
    provider: str,
    base_url: str | None,
    payload: dict[str, Any],
    expected: list[str],
) -> None:
    client = FakeHTTPClient(FakeResponse(payload))

    models = asyncio.run(
        list_available_models(
            provider=provider,  # type: ignore[arg-type]
            api_key="test-key",
            base_url=base_url,
            client=client,
        )
    )

    assert models == expected
    assert client.request is not None
    url, request = client.request
    if provider == "openai-compatible":
        assert url == "https://llm.example/v1/models"
    if provider == "alpineai":
        assert url == "https://api.prod.alpineai.ch/v1/models"
    assert request["headers"]["Authorization"] == "Bearer test-key"


def test_anthropic_model_discovery_uses_native_auth_headers() -> None:
    client = FakeHTTPClient(FakeResponse({"data": [{"id": "claude-model"}]}))

    models = asyncio.run(
        list_available_models(provider="anthropic", api_key="test-key", client=client)
    )

    assert models == ["claude-model"]
    assert client.request is not None
    url, request = client.request
    assert url == "https://api.anthropic.com/v1/models"
    assert request["headers"]["x-api-key"] == "test-key"
    assert request["headers"]["anthropic-version"] == "2023-06-01"


def test_model_discovery_requires_key_and_compatible_endpoint() -> None:
    with pytest.raises(ModelDiscoveryError, match="environment variable is empty"):
        asyncio.run(list_available_models(provider="alpineai", api_key=""))
    with pytest.raises(ModelDiscoveryError, match="base URL"):
        asyncio.run(
            list_available_models(provider="openai-compatible", api_key="test-key")
        )


def test_model_discovery_reports_empty_or_failed_model_list_safely() -> None:
    client = FakeHTTPClient(FakeResponse({"data": []}))
    with pytest.raises(ModelDiscoveryError, match="no selectable model IDs"):
        asyncio.run(
            list_available_models(provider="alpineai", api_key="test-key", client=client)
        )

    failed_client = FakeHTTPClient(FakeResponse({"error": "unauthorized"}, status_code=401))
    with pytest.raises(ModelDiscoveryError, match="HTTP 401") as error:
        asyncio.run(
            list_available_models(
                provider="alpineai", api_key="private-value", client=failed_client
            )
        )
    assert "private-value" not in str(error.value)
