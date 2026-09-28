import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.gui.workspace import (
    VersionSelection,
    WorkspacePersistenceError,
    WorkspaceProject,
    WorkspaceSettings,
    WorkspaceStore,
)


def test_workspace_settings_round_trip_without_secret_values(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings" / "gui.json"
    store = WorkspaceStore(settings_path)
    settings = WorkspaceSettings(
        catalogue_directory="data/questionnaires/json",
        default_export_format="redcap_csv",
        llm_provider="openai-compatible",
        llm_model="institutional-model",
        llm_base_url="https://llm.example.edu/v1",
        llm_api_key_environment="SWISSGPT_API_KEY",
        remote_processing_enabled=False,
    )

    store.save_settings(settings)
    loaded = store.load_settings()
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))

    assert loaded == settings
    assert "SWISSGPT_API_KEY" == loaded.llm_api_key_environment
    assert not any("secret" in key.casefold() or "token" in key.casefold() for key in persisted)


def test_workspace_settings_default_on_first_run(tmp_path: Path) -> None:
    settings = WorkspaceStore(tmp_path / "missing.json").load_settings()

    assert settings.llm_provider == "openai"
    assert settings.remote_processing_enabled is False


def test_workspace_project_round_trip_preserves_selections_and_steps(
    tmp_path: Path,
) -> None:
    project = WorkspaceProject(name="Depression screening review").model_copy(
        update={
            "selections": [
                VersionSelection(
                    instrument_id="phq9", version_id="phq9_en_v1", item_ids=["phq9_en_01"]
                )
            ]
        }
    ).record_step(
        "version_selected", "Selected PHQ-9 English version", "phq9/phq9_en_v1"
    )
    project_path = tmp_path / "project.psymetriq.json"

    WorkspaceStore.save_project(project_path, project)
    loaded = WorkspaceStore.load_project(project_path)

    assert loaded.project_id == project.project_id
    assert loaded.selections == project.selections
    assert loaded.workflow_steps == project.workflow_steps


def test_duplicate_version_selection_is_rejected() -> None:
    with pytest.raises(ValidationError, match="selected only once"):
        WorkspaceProject(
            name="Duplicate selections",
            selections=[
                VersionSelection(instrument_id="phq9", version_id="v1"),
                VersionSelection(instrument_id="phq9", version_id="v1"),
            ],
        )


def test_invalid_saved_project_does_not_leak_validation_values(tmp_path: Path) -> None:
    project_path = tmp_path / "invalid.json"
    project_path.write_text('{"name":"","private":"do-not-log"}', encoding="utf-8")

    with pytest.raises(WorkspacePersistenceError) as error_info:
        WorkspaceStore.load_project(project_path)

    assert "do-not-log" not in str(error_info.value)


def test_failed_atomic_settings_write_removes_temporary_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings_path = tmp_path / "settings.json"

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("src.gui.workspace.os.replace", fail_replace)

    with pytest.raises(WorkspacePersistenceError, match="Could not save settings.json"):
        WorkspaceStore(settings_path).save_settings(WorkspaceSettings())

    assert not settings_path.exists()
    assert list(tmp_path.glob("*.tmp")) == []
