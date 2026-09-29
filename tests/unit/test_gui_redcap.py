"""GUI-level tests for the live REDCap connect/push/pull workflow."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.exporters.redcap_api import RedcapApiError, RedcapProjectSummary
from src.gui import application
from src.gui.application import PsyMetriQApplication


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


def test_redcap_connect_failure_sets_a_status_message_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    app.settings = app.settings.model_copy(update={"redcap_api_url": "https://example.org/api/"})
    monkeypatch.setenv("REDCAP_API_TOKEN", "fake-token")

    def fake_connect(url: str, token: str) -> Any:
        raise RedcapApiError("Could not connect to the REDCap project; check the API URL and token")

    monkeypatch.setattr(application, "redcap_connect", fake_connect)

    asyncio.run(app._redcap_connect(None))

    assert app.redcap_project is None
    assert "fehlgeschlagen" in app.redcap_status_message


def test_redcap_connect_success_stores_project_and_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    app.settings = app.settings.model_copy(update={"redcap_api_url": "https://example.org/api/"})
    monkeypatch.setenv("REDCAP_API_TOKEN", "fake-token")
    fake_project = object()
    monkeypatch.setattr(application, "redcap_connect", lambda url, token: fake_project)
    monkeypatch.setattr(
        application,
        "redcap_describe_project",
        lambda project: RedcapProjectSummary(
            project_id="7", project_title="My Study", is_longitudinal=False
        ),
    )

    asyncio.run(app._redcap_connect(None))

    assert app.redcap_project is fake_project
    assert app.redcap_project_summary is not None
    assert "My Study" in app.redcap_status_message


def test_redcap_push_without_connection_sets_an_error_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    _select_free_version(app)

    asyncio.run(app._redcap_push(None))

    assert app.status_is_error is True


def test_redcap_push_shows_a_confirmation_dialog_before_pushing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    _select_free_version(app)
    app.redcap_project = object()
    app.redcap_project_summary = RedcapProjectSummary(
        project_id="7", project_title="My Study", is_longitudinal=False
    )
    pushed: dict[str, Any] = {}

    def fake_push(project: Any, questionnaire: Any, version: Any) -> Any:
        pushed["called"] = True
        return SimpleNamespace(form_name="phq9", pushed_field_count=10, total_field_count=10)

    monkeypatch.setattr(application, "push_questionnaire_to_project", fake_push)

    async def _confirm_after_dialog() -> None:
        while not app.page.dialogs:
            await asyncio.sleep(0)
        dialog = app.page.dialogs[-1]
        confirm_button = dialog.actions[-1]
        result = confirm_button.on_click(None)
        if asyncio.iscoroutine(result):
            await result

    async def _run() -> None:
        await asyncio.gather(app._redcap_push(None), _confirm_after_dialog())

    asyncio.run(_run())

    assert pushed.get("called") is True
    assert "Gepusht" in app.redcap_status_message


def test_redcap_pull_imports_into_the_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    app.redcap_project = object()
    # Redirect the catalog store to an isolated directory: import_families()
    # writes a new file, and this must never touch the real, shared catalog.
    from src.gui.catalog_store import QuestionnaireCatalogStore

    isolated_catalog_directory = tmp_path / "isolated_catalog"
    isolated_catalog_directory.mkdir()
    app.settings = app.settings.model_copy(
        update={"catalogue_directory": str(isolated_catalog_directory)}
    )
    app.catalog_store = QuestionnaireCatalogStore(isolated_catalog_directory)
    app.catalog_records = []

    from schemas.questionnaire_schema import (
        ItemSchema,
        QuestionnaireParent,
        QuestionnaireVersion,
        ResponseOption,
    )

    imported_family = QuestionnaireParent(
        instrument_id="redcap_pulled",
        name_full="Pulled Instrument",
        is_commercial=None,
        versions=[
            QuestionnaireVersion(
                version_id="redcap_import_v1",
                language="en",
                response_sets={
                    "s": [
                        ResponseOption(code=0, label="No", score=None),
                        ResponseOption(code=1, label="Yes", score=None),
                    ]
                },
                items=[
                    ItemSchema(
                        item_id="q1",
                        variable_name="q1",
                        dimension="core",
                        prompt_text="Pulled item",
                        response_set_ref="s",
                    )
                ],
            )
        ],
    )
    monkeypatch.setattr(
        application, "pull_questionnaire_from_project", lambda project, language: imported_family
    )

    asyncio.run(app._redcap_pull(None))

    assert any(
        family.instrument_id == "redcap_pulled" for family, _path in app.catalog_records
    )
    assert "redcap_pulled" in app.redcap_status_message
