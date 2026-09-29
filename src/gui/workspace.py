"""Versioned, portable GUI settings and questionnaire assembly projects."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

LOGGER = logging.getLogger(__name__)

ExportFormat = Literal["psymetriq_json", "fhir_json", "xlsx", "item_csv", "redcap_csv"]
ProviderName = Literal["openai", "anthropic", "alpineai", "openai-compatible"]
ThemeModeSetting = Literal["light", "dark"]
FontSizeSetting = Literal["small", "normal", "large"]
WorkflowAction = Literal[
    "catalog_import",
    "catalog_reload",
    "version_selected",
    "version_removed",
    "selection_reordered",
    "items_updated",
    "scale_selected",
    "scale_removed",
    "exported",
    "project_saved",
    "project_loaded",
    "settings_saved",
]


class WorkspaceSettings(BaseModel):
    """Non-secret application preferences, serializable as versioned JSON."""

    settings_schema_version: Literal[1] = 1
    catalogue_directory: str = "data/questionnaires/json"
    export_directory: str = "data/03_export_artifacts"
    pdf_inbox_directory: str = "data/questionnaires/inbox"
    pdf_review_directory: str = "data/questionnaires/review"
    default_language: str = "en"
    default_export_format: ExportFormat = "psymetriq_json"
    theme_mode: ThemeModeSetting = "light"
    font_size: FontSizeSetting = "normal"
    enable_ocr: bool = True
    ocr_languages: str = "eng+deu"
    maximum_pdf_size_mib: int = Field(default=40, ge=1, le=200)
    maximum_pdf_pages: int = Field(default=500, ge=1, le=2000)
    maximum_extracted_characters: int = Field(default=120_000, ge=1000, le=500_000)
    minimum_extracted_characters: int = Field(default=160, ge=1, le=20_000)
    extraction_confidence_threshold: float = Field(default=0.92, ge=0, le=1)
    watcher_poll_seconds: float = Field(default=3.0, ge=0.5, le=600)
    llm_provider: ProviderName = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_api_key_environment: str = "OPENAI_API_KEY"
    remote_processing_enabled: bool = False
    acknowledged_licenses: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "instrument_id -> ISO 8601 timestamp of a local, one-time confirmation that "
            "this installation's user has read and will follow that instrument's license "
            "terms. This is a local usage acknowledgment, not a redistribution approval."
        ),
    )

    @field_validator("llm_api_key_environment")
    @classmethod
    def validate_environment_variable_name(cls, value: str) -> str:
        """Permit only a variable name, never a value that could contain a secret."""
        if not value or not value.replace("_", "").isalnum() or value[0].isdigit():
            raise ValueError("API key setting must be an environment variable name")
        return value

    @model_validator(mode="after")
    def validate_compatible_provider(self) -> WorkspaceSettings:
        """Require an endpoint before an OpenAI-compatible provider is selectable."""
        if self.llm_provider == "openai-compatible" and not self.llm_base_url:
            raise ValueError("An OpenAI-compatible provider requires an API base URL")
        return self


class VersionSelection(BaseModel):
    """Reference a version in the current catalogue without copying licensed text."""

    instrument_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    item_ids: list[str] = Field(default_factory=list)
    item_adaptations: list[ItemAdaptation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_adaptation_ids(self) -> VersionSelection:
        adaptation_ids = [adaptation.item_id for adaptation in self.item_adaptations]
        if len(adaptation_ids) != len(set(adaptation_ids)):
            raise ValueError("Each selected item may have only one active adaptation")
        if self.item_ids and not set(adaptation_ids).issubset(self.item_ids):
            raise ValueError("Adaptations must reference items selected in this project")
        return self


class ItemAdaptation(BaseModel):
    """A study-specific wording change kept separate from the catalog source item."""

    item_id: str = Field(min_length=1)
    adapted_prompt_text: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=1000)
    adapted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowStep(BaseModel):
    """A non-sensitive record of a completed import, selection, or export action."""

    action: WorkflowAction
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(
        default=None,
        description="An instrument/version ID or relative export filename; no item text.",
    )


class WorkspaceProject(BaseModel):
    """A saveable questionnaire-building session with stable catalog references."""

    project_schema_version: Literal[1] = 1
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    catalogue_directory: str = "data/questionnaires/json"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    selections: list[VersionSelection] = Field(default_factory=list)
    workflow_steps: list[WorkflowStep] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def ensure_unique_version_selections(self) -> WorkspaceProject:
        """Disallow duplicate instrument/version pairs in a saved assembly."""
        keys = [(entry.instrument_id, entry.version_id) for entry in self.selections]
        if len(keys) != len(set(keys)):
            raise ValueError("Each instrument version may be selected only once")
        return self

    def record_step(
        self,
        action: WorkflowAction,
        summary: str,
        reference: str | None = None,
    ) -> WorkspaceProject:
        """Return an updated project with a capped append-only workflow history."""
        return self.model_copy(
            update={
                "updated_at": datetime.now(timezone.utc),
                "workflow_steps": [
                    *self.workflow_steps,
                    WorkflowStep(action=action, summary=summary, reference=reference),
                ][-500:],
            }
        )


class WorkspacePersistenceError(RuntimeError):
    """Raised when settings or project data cannot safely be loaded or saved."""


class WorkspaceStore:
    """Persist settings and project snapshots using atomic local JSON files."""

    def __init__(self, settings_path: Path | str) -> None:
        self.settings_path = Path(settings_path)

    def load_settings(self) -> WorkspaceSettings:
        """Read validated settings or return defaults on first run."""
        if not self.settings_path.exists():
            return WorkspaceSettings()
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return WorkspaceSettings.model_validate(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
            LOGGER.error("Could not validate GUI settings (%s)", type(error).__name__)
            raise WorkspacePersistenceError("The settings file is invalid") from None

    def save_settings(self, settings: WorkspaceSettings) -> None:
        """Write non-secret settings atomically, creating the parent directory."""
        self._write_json(self.settings_path, settings.model_dump(mode="json"))

    @classmethod
    def save_project(cls, path: Path | str, project: WorkspaceProject) -> None:
        """Write a complete portable project snapshot to the selected path."""
        cls._write_json(Path(path), project.model_dump(mode="json"))

    @staticmethod
    def load_project(path: Path | str) -> WorkspaceProject:
        """Load and validate a saved project without relying on a database."""
        source = Path(path)
        try:
            content = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            LOGGER.error(
                "Could not load workspace project %s (%s)",
                source.name,
                type(error).__name__,
            )
            raise WorkspacePersistenceError(
                f"The project file {source.name} is invalid"
            ) from None
        return WorkspaceStore.load_project_content(content, source.name)

    @staticmethod
    def load_project_content(
        content: str, source_name: str = "project.json"
    ) -> WorkspaceProject:
        """Validate uploaded project JSON when a browser provides bytes, not a path."""
        try:
            payload = json.loads(content)
            return WorkspaceProject.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as error:
            LOGGER.error(
                "Could not load workspace project %s (%s)",
                source_name,
                type(error).__name__,
            )
            raise WorkspacePersistenceError(
                f"The project file {source_name} is invalid"
            ) from None

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        """Flush a sibling temporary file before atomically replacing the target."""
        temporary_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            LOGGER.error(
                "Could not persist workspace JSON %s (%s)",
                path.name,
                type(error).__name__,
            )
            raise WorkspacePersistenceError(f"Could not save {path.name}") from None
