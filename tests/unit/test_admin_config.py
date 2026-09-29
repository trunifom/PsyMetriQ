"""Tests for admin-only deployment feature flags.

These flags are read once from a local file the operator controls; they are
never exposed in the GUI settings screen and never change what the intake
pipeline treats as a rights-approved, redistributable document.
"""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    ResponseOption,
)
from src.gui import application
from src.gui.admin_config import AdminConfig, AdminConfigError, AdminConfigStore
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


def _commercial_family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "agree_5": [
                ResponseOption(code=0, label="Never", score=0),
                ResponseOption(code=1, label="Always", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="item_01",
                variable_name="item_01",
                dimension="core",
                prompt_text="A licensed synthetic test item.",
                response_set_ref="agree_5",
            )
        ],
        source_documents=[
            QuestionnaireSourceDocument(
                title="Licensed Test Manual",
                document_type="questionnaire_form",
                language="en",
                source_url="https://example.org/licensed-test",
                license_name="Commercial Publisher License",
                redistribution_permitted=True,
                permission_basis="Institutional test library license for this study.",
                accessed_on=date(2026, 1, 1),
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id="licensed_demo",
        name_full="Licensed Demonstration Instrument",
        is_commercial=True,
        versions=[version],
    )


def _app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: dict[str, object] | None = None
) -> PsyMetriQApplication:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    admin_config_path = tmp_path / "admin_config.json"
    if admin_config is not None:
        admin_config_path.write_text(json.dumps(admin_config), encoding="utf-8")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", admin_config_path)
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    app.catalog_records.append((_commercial_family(), Path("synthetic.json")))
    return app


def test_missing_admin_config_file_defaults_to_all_features_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path, admin_config=None)

    assert app.admin_config.license_acknowledgment_enabled is True
    assert app.admin_config.remote_processing_allowed is True
    assert app.admin_config.hidden_views == []


def test_disabling_license_acknowledgment_skips_the_gate_entirely(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(
        monkeypatch, tmp_path, admin_config={"license_acknowledgment_enabled": False}
    )
    family, version = app._find_version("licensed_demo", "v1")

    app._toggle_version(family, version, True)

    assert app._project_selection("licensed_demo", "v1") is not None
    assert app.page.dialogs == []


def test_hidden_views_are_removed_from_the_sidebar_and_navigation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path, admin_config={"hidden_views": ["intake", "settings"]})

    assert "intake" not in app.nav_buttons
    assert "settings" not in app.nav_buttons
    assert app.active_view not in {"intake", "settings"}

    app._navigate("intake")
    assert app.active_view != "intake"


def test_remote_processing_kill_switch_overrides_the_user_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path, admin_config={"remote_processing_allowed": False})
    app.settings = app.settings.model_copy(update={"remote_processing_enabled": True})

    assert app._remote_processing_enabled() is False


def test_invalid_admin_config_file_falls_back_to_defaults_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    admin_config_path = tmp_path / "admin_config.json"
    admin_config_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", admin_config_path)

    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]

    assert app.admin_config == AdminConfig()
    assert app.startup_warning is not None


def test_admin_config_store_load_rejects_unknown_view_names(tmp_path: Path) -> None:
    path = tmp_path / "admin_config.json"
    path.write_text(json.dumps({"hidden_views": ["not_a_real_view"]}), encoding="utf-8")

    with pytest.raises(AdminConfigError):
        AdminConfigStore(path).load()


def test_institutionally_licensed_instrument_skips_the_gate_without_user_acknowledgment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(
        monkeypatch,
        tmp_path,
        admin_config={"institutionally_licensed_instruments": ["licensed_demo"]},
    )
    family, version = app._find_version("licensed_demo", "v1")

    app._toggle_version(family, version, True)

    assert app._project_selection("licensed_demo", "v1") is not None
    assert app.page.dialogs == []
    assert app._is_license_acknowledged(family) is False  # unlocked institutionally, not per-user


def test_only_the_listed_instrument_is_institutionally_unlocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(
        monkeypatch,
        tmp_path,
        admin_config={"institutionally_licensed_instruments": ["some_other_instrument"]},
    )
    family, version = app._find_version("licensed_demo", "v1")

    app._toggle_version(family, version, True)

    assert app._project_selection("licensed_demo", "v1") is None
    assert len(app.page.dialogs) == 1


def test_version_card_shows_institutional_license_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(
        monkeypatch,
        tmp_path,
        admin_config={"institutionally_licensed_instruments": ["licensed_demo"]},
    )
    family, version = app._find_version("licensed_demo", "v1")

    card = app._version_card(family, version)
    subtitle = card.content.controls[1].content.controls[2].value

    assert "Institutionell lizenziert" in subtitle
