import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from src.ingestion import llm_extractor
from src.ingestion.document_pipeline import _create_remote_extractor
from src.ingestion.llm_extractor import (
    AnthropicQuestionnaireExtractor,
    OpenAIQuestionnaireExtractionResponse,
    QuestionnaireExtractionError,
    create_questionnaire_extractor,
)


class FakeAnthropicMessages:
    def __init__(self, parsed_output: OpenAIQuestionnaireExtractionResponse) -> None:
        self.parsed_output = parsed_output
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[
                SimpleNamespace(
                    type="text",
                    text=self.parsed_output.model_dump_json(),
                )
            ],
        )


def test_anthropic_extractor_uses_shared_strict_dto_and_maps_response() -> None:
    parsed = OpenAIQuestionnaireExtractionResponse(
        document_kind="unknown",
        extraction_confidence=0.2,
    )
    endpoint = FakeAnthropicMessages(parsed)
    extractor = AnthropicQuestionnaireExtractor(
        api_key="test-key",
        model="claude-sonnet-test",
        client=SimpleNamespace(messages=endpoint),
    )

    draft = asyncio.run(
        extractor.extract(filename="document.pdf", extracted_text="Synthetic source text")
    )

    assert endpoint.request is not None
    assert endpoint.request["model"] == "claude-sonnet-test"
    assert endpoint.request["max_tokens"] == 32_000
    assert "JSON Schema" in endpoint.request["system"]
    assert "output_format" not in endpoint.request
    assert "Synthetic source text" in endpoint.request["messages"][0]["content"]
    assert draft.document_kind == "unknown"
    assert draft.extraction_confidence == 0.2


def test_anthropic_refusal_is_reported_without_accepting_a_draft() -> None:
    parsed = OpenAIQuestionnaireExtractionResponse(
        document_kind="unknown",
        extraction_confidence=0.2,
    )

    class RefusingMessages(FakeAnthropicMessages):
        async def create(self, **kwargs: Any) -> Any:
            self.request = kwargs
            return SimpleNamespace(
                stop_reason="refusal",
                content=[],
            )

    extractor = AnthropicQuestionnaireExtractor(
        api_key="test-key",
        client=SimpleNamespace(messages=RefusingMessages(parsed)),
    )

    with pytest.raises(QuestionnaireExtractionError, match="refused document"):
        asyncio.run(extractor.extract(filename="private.pdf", extracted_text="source"))


def test_anthropic_invalid_json_is_rejected_by_local_pydantic_validation() -> None:
    class InvalidJSONMessages:
        async def create(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="not-json")],
            )

    extractor = AnthropicQuestionnaireExtractor(
        api_key="test-key",
        client=SimpleNamespace(messages=InvalidJSONMessages()),
    )

    with pytest.raises(QuestionnaireExtractionError, match="invalid for bad.json.pdf"):
        asyncio.run(extractor.extract(filename="bad.json.pdf", extracted_text="source"))


def test_provider_factory_builds_native_anthropic_client() -> None:
    extractor = create_questionnaire_extractor(
        provider="anthropic",
        api_key="test-key",
        model="claude-sonnet-test",
    )

    assert isinstance(extractor, AnthropicQuestionnaireExtractor)
    assert extractor.model == "claude-sonnet-test"


def test_provider_factory_requires_endpoint_for_openai_compatible_services() -> None:
    with pytest.raises(ValueError, match="requires a configured base_url"):
        create_questionnaire_extractor(
            provider="openai-compatible",
            api_key="test-key",
            model="swiss-model",
        )


def test_provider_factory_routes_compatible_endpoint_to_openai_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_openai_extractor(**kwargs: Any) -> object:
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(llm_extractor, "OpenAIQuestionnaireExtractor", fake_openai_extractor)

    create_questionnaire_extractor(
        provider="openai-compatible",
        api_key="test-key",
        model="swiss-model",
        base_url="https://llm.example.org/v1",
    )

    assert observed == {
        "api_key": "test-key",
        "model": "swiss-model",
        "base_url": "https://llm.example.org/v1",
    }


def test_swissgpt_environment_settings_are_passed_without_logging_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_factory(**kwargs: Any) -> object:
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(
        "src.ingestion.document_pipeline.create_questionnaire_extractor", fake_factory
    )
    monkeypatch.setenv("SWISSGPT_API_KEY", "test-secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://swissgpt.example.org/v1")
    monkeypatch.setenv("LLM_MODEL", "swiss-model")

    _create_remote_extractor(
        provider="openai-compatible",
        model=None,
        base_url=None,
        api_key_env="SWISSGPT_API_KEY",
    )

    assert observed == {
        "provider": "openai-compatible",
        "api_key": "test-secret",
        "model": "swiss-model",
        "base_url": "https://swissgpt.example.org/v1",
    }


def test_swissgpt_provider_requires_explicit_api_key_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SWISSGPT_API_KEY", raising=False)

    with pytest.raises(ValueError, match="SWISSGPT_API_KEY is required"):
        _create_remote_extractor(
            provider="openai-compatible",
            model="swiss-model",
            base_url="https://swissgpt.example.org/v1",
            api_key_env="SWISSGPT_API_KEY",
        )


def test_anthropic_provider_does_not_inherit_compatible_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_factory(**kwargs: Any) -> object:
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(
        "src.ingestion.document_pipeline.create_questionnaire_extractor", fake_factory
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://compatible.example.org/v1")

    _create_remote_extractor(
        provider="anthropic",
        model=None,
        base_url=None,
        api_key_env=None,
    )

    assert observed["provider"] == "anthropic"
    assert observed["base_url"] is None
