"""Admin-only, deployment-wide feature flags, read from a local file at startup.

Unlike ``WorkspaceSettings`` (per-installation preferences a user can change
from the Einstellungen screen and that round-trip through settings
export/import), this configuration is never exposed in the GUI and is not
part of any export. An administrator with server/file access edits the JSON
file directly; the running application only reads it once at startup.

This can only hide already-safe UI affordances (a sidebar entry) or skip a
local usage confirmation (the license-acknowledgment dialog, intended for
test/debug or a trusted single-admin deployment); it never changes what the
PDF intake pipeline treats as a rights-approved, redistributable document.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

LOGGER = logging.getLogger(__name__)

WorkspaceViewName = Literal["catalog", "project", "exchange", "intake", "settings"]
ALL_VIEW_NAMES: tuple[WorkspaceViewName, ...] = (
    "catalog",
    "project",
    "exchange",
    "intake",
    "settings",
)


class AdminConfigError(RuntimeError):
    """Raised when the admin configuration file exists but cannot be parsed."""


class AdminConfig(BaseModel):
    """Deployment-wide toggles set by the operator, not by application users."""

    admin_config_schema_version: Literal[1] = 1
    license_acknowledgment_enabled: bool = Field(
        default=True,
        description=(
            "False skips the local per-instrument license acknowledgment dialog "
            "entirely, for test/debug or a trusted single-admin deployment. It "
            "does not affect the intake pipeline's rights sidecar gate."
        ),
    )
    remote_processing_allowed: bool = Field(
        default=True,
        description=(
            "Deployment-wide kill switch for remote LLM PDF extraction; false "
            "disables it for every user regardless of their own settings."
        ),
    )
    hidden_views: list[WorkspaceViewName] = Field(
        default_factory=list,
        description="Sidebar navigation entries to hide from every user.",
    )
    institutionally_licensed_instruments: list[str] = Field(
        default_factory=list,
        description=(
            "instrument_id values the institution (e.g. its library/licensing office) "
            "has confirmed hold a valid license. The per-user, per-instrument license "
            "acknowledgment dialog is skipped entirely for every user for exactly these "
            "instruments; every other commercial instrument still requires each user's "
            "own one-time click-through. This is an operator-only allowlist: no in-app "
            "action by a regular user can add to it. It still does not affect what the "
            "PDF intake pipeline is willing to publish -- an instrument only ever reaches "
            "this list because item text for it was already legitimately catalogued "
            "through that rights-gated pipeline."
        ),
    )
    feature_flags: dict[str, bool] = Field(
        default_factory=dict,
        description="Free-form named toggles reserved for future ad-hoc feature gating.",
    )


class AdminConfigStore:
    """Load the admin configuration file, defaulting to all features enabled."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AdminConfig:
        if not self.path.is_file():
            return AdminConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return AdminConfig.model_validate(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
            LOGGER.error("Could not validate admin config (%s)", type(error).__name__)
            raise AdminConfigError("The admin config file is invalid") from None
