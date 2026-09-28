"""Discover model IDs available to the configured remote provider account."""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

LOGGER = logging.getLogger(__name__)
ModelProviderName = Literal["openai", "anthropic", "alpineai", "openai-compatible"]
ALPINEAI_BASE_URL = "https://api.prod.alpineai.ch/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"


class ModelDiscoveryError(RuntimeError):
    """Raised when model IDs cannot be listed or parsed safely."""


def _model_ids(payload: Any) -> list[str]:
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ModelDiscoveryError("Provider response does not contain a model list")
    names = {
        record if isinstance(record, str) else record.get("id")
        for record in records
        if isinstance(record, str) or isinstance(record, dict)
    }
    model_ids = sorted(name.strip() for name in names if isinstance(name, str) and name.strip())
    if not model_ids:
        raise ModelDiscoveryError("Provider returned no selectable model IDs")
    return model_ids


async def list_available_models(
    *,
    provider: ModelProviderName,
    api_key: str,
    base_url: str | None = None,
    client: Any | None = None,
) -> list[str]:
    """Fetch model IDs using provider-specific auth and OpenAI-compatible model endpoints."""
    if not api_key.strip():
        raise ModelDiscoveryError("The configured API key environment variable is empty")
    if provider == "openai-compatible" and not base_url:
        raise ModelDiscoveryError("Set the OpenAI-compatible API base URL before loading models")

    if provider == "anthropic":
        url = ANTHROPIC_MODELS_URL
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "accept": "application/json",
        }
        params = {"limit": 1000}
    else:
        api_base = base_url or (
            ALPINEAI_BASE_URL if provider == "alpineai" else OPENAI_BASE_URL
        )
        url = f"{api_base.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}", "accept": "application/json"}
        params = None

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=20.0)
    try:
        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return _model_ids(response.json())
    except ModelDiscoveryError:
        raise
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        LOGGER.warning("Provider model listing returned HTTP %s", status_code)
        raise ModelDiscoveryError(f"Provider model listing failed (HTTP {status_code})") from None
    except (httpx.HTTPError, ValueError, TypeError) as error:
        LOGGER.warning("Could not read model list from provider (%s)", type(error).__name__)
        raise ModelDiscoveryError("Could not retrieve or parse the provider model list") from None
    finally:
        if owns_client:
            await http_client.aclose()
