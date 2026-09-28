from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

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


def test_gui_starts_with_validated_catalog_and_renders_each_workspace_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    page = FakePage()

    app = PsyMetriQApplication(page)  # type: ignore[arg-type]

    assert len(app.catalog_records) == 5
    assert app.search_field.label == "Suche"
    assert len(page.controls) == 1
    for view in ("project", "exchange", "intake", "settings", "catalog"):
        app._navigate(view)
        assert app.active_view == view
        assert page.update_count > 0
    assert app.header_title.value == "Instrumentenbibliothek"
    assert app.nav_buttons["catalog"].bgcolor == "#28685D"
    assert app.nav_buttons["project"].bgcolor == "#1B4941"

    family = next(family for family, _path in app.catalog_records if family.instrument_id == "phq9")
    app._toggle_version(family, family.versions[0], True)
    assert "1 Versionen im Projekt" in app.header_summary.value


def test_gui_version_selection_generates_interoperable_export_preview(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    family = next(
        record
        for record, _path in app.catalog_records
        if record.instrument_id == "phq9"
    )
    version = family.versions[0]

    app._toggle_version(family, version, True)
    app._navigate("exchange")

    assert len(app._selected_versions()) == 1
    assert "phq9" in app.export_preview.value
    assert "Little interest" in app.export_preview.value

    app._set_export_format("xlsx")

    assert "XLSX-Arbeitsmappe" in app.export_preview.value
    assert "Antwortoptionen" in app.export_preview.value


def test_settings_form_exposes_intake_limits_and_ocr_preferences(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    app._navigate("settings")

    assert app.inbox_path_field.value.endswith("questionnaires/inbox")
    assert app.review_path_field.value.endswith("questionnaires/review")
    assert app.ocr_switch.value is True
    assert app.maximum_pdf_size_field.value == "40"
    assert app.confidence_threshold_field.value == "0.92"


def test_gui_help_opens_explanation_and_example(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    page = FakePage()
    app = PsyMetriQApplication(page)  # type: ignore[arg-type]

    app._show_help("Dateiformat", "Importiert strukturierte Daten.", "Beispiel: FHIR R4 JSON")

    dialog = page.dialogs[-1]
    assert dialog.modal is True
    assert dialog.title.value == "Dateiformat"
    assert len(dialog.content.controls) == 3


def test_catalogue_filters_limit_versions_by_locale_and_rights_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    all_versions = app._visible_versions()
    locale = next(
        version.locale
        for _family, version in all_versions
        if version.locale is not None
    )

    app.locale_filter = locale.casefold()
    locale_matches = app._visible_versions()
    assert locale_matches
    assert all(
        version.locale.casefold() == locale.casefold()
        for _family, version in locale_matches
    )

    family, path = app.catalog_records[0]
    unknown_family = family.model_copy(
        update={"instrument_id": "synthetic_unknown_rights", "is_commercial": None}
    )
    app.catalog_records.append((unknown_family, path))
    app.locale_filter = "all"
    app.commercial_filter = "unknown"
    unknown_rights = app._visible_versions()
    assert unknown_rights
    assert all(family.is_commercial is None for family, _version in unknown_rights)


def test_score_scale_group_selection_adds_all_target_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    family = next(
        family for family, _path in app.catalog_records if family.instrument_id == "dass21"
    )
    version = family.versions[0]
    scale = version.scoring_algorithms[0]

    app._toggle_item_group(
        family,
        version,
        scale.target_items,
        True,
        is_scale=True,
        label=scale.output_variable,
    )

    selection = app._project_selection(family.instrument_id, version.version_id)
    assert selection is not None
    assert set(selection.item_ids) == set(scale.target_items)


def test_item_adaptation_dialog_saves_reason_without_changing_source_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    page = FakePage()
    app = PsyMetriQApplication(page)  # type: ignore[arg-type]
    family = next(family for family, _path in app.catalog_records if family.instrument_id == "phq9")
    version = family.versions[0]
    item = version.items[0]
    original_prompt = item.prompt_text

    app._edit_item_prompt(family, version, item.item_id)
    dialog = page.dialogs[-1]
    prompt_field = dialog.content.controls[1]
    reason_field = dialog.content.controls[2]
    prompt_field.value = "Study-adapted wording for the target population"
    reason_field.value = "Cognitive interviews found the source wording unclear"
    save_button = next(
        action for action in dialog.actions if action.content == "Im Projekt übernehmen"
    )
    save_button.on_click(None)

    selection = app._project_selection(family.instrument_id, version.version_id)
    assert selection is not None
    assert selection.item_adaptations[0].adapted_prompt_text == prompt_field.value
    assert "Cognitive interviews" in selection.item_adaptations[0].reason
    assert family.versions[0].items[0].prompt_text == original_prompt
