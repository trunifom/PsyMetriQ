"""GUI-level tests for pushing an exported instrument version to Zotero."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.gui import application
from src.gui.application import PsyMetriQApplication
from src.ingestion.zotero_source import ZoteroPushResult, ZoteroSourceError


class FakePage:
    def __init__(self) -> None:
        self.services: list[Any] = []
        self.window = SimpleNamespace(min_width=None, min_height=None)
        self.controls: list[Any] = []
        self.update_count = 0
        self.dialogs: list[Any] = []

    def add(self, *controls: Any) -> None:
        self.controls.extend(controls)

    def update(self, *_controls: Any) -> None:
        self.update_count += 1

    def show_dialog(self, dialog: Any) -> None:
        self.dialogs.append(dialog)

    def pop_dialog(self) -> Any:
        return self.dialogs.pop() if self.dialogs else None


def _app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PsyMetriQApplication:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", tmp_path / "admin_config.json")
    return PsyMetriQApplication(FakePage())  # type: ignore[arg-type]


def _select_free_version(app: PsyMetriQApplication) -> None:
    family = next(
        family for family, _path in app.catalog_records if family.instrument_id == "phq9"
    )
    version = next(version for version in family.versions if version.item_text_included)
    app._toggle_version(family, version, True)


def test_push_to_zotero_requires_credentials_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    _select_free_version(app)
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)

    asyncio.run(app._push_to_zotero(None))

    assert app.status_is_error is True


def test_push_to_zotero_requires_a_selected_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    monkeypatch.setenv("ZOTERO_API_KEY", "fake-key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")

    asyncio.run(app._push_to_zotero(None))

    assert app.status_is_error is True


def test_push_to_zotero_exports_the_selected_version_and_reports_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    _select_free_version(app)
    monkeypatch.setenv("ZOTERO_API_KEY", "fake-key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")
    captured: dict[str, Any] = {}

    def fake_push(config: Any, *, questionnaire: Any, version: Any, export_file_path: Path) -> Any:
        captured["questionnaire"] = questionnaire
        captured["version"] = version
        captured["export_file_path"] = export_file_path
        assert export_file_path.is_file()
        return ZoteroPushResult(item_key="ZOTKEY1", attached_file=export_file_path.name)

    monkeypatch.setattr(application, "push_questionnaire_to_zotero", fake_push)

    asyncio.run(app._push_to_zotero(None))

    assert app.status_is_error is False
    assert "ZOTKEY1" in app.status_message
    assert captured["questionnaire"].instrument_id == "phq9"
    # The temporary export file is cleaned up after the push completes.
    assert not captured["export_file_path"].exists()


def test_push_to_zotero_reports_a_failed_item_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    _select_free_version(app)
    monkeypatch.setenv("ZOTERO_API_KEY", "fake-key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")

    def fake_push(config: Any, *, questionnaire: Any, version: Any, export_file_path: Path) -> Any:
        raise ZoteroSourceError("Could not create the Zotero item")

    monkeypatch.setattr(application, "push_questionnaire_to_zotero", fake_push)

    asyncio.run(app._push_to_zotero(None))

    assert app.status_is_error is True
