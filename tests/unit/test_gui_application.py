import asyncio
import io
import json
import zipfile
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


class FakeSaveFilePicker:
    def __init__(self) -> None:
        self.payload: bytes | None = None

    async def save_file(self, **kwargs: Any) -> str:
        self.payload = kwargs["src_bytes"]
        return "study-reference-export.zip"


def test_gui_starts_with_validated_catalog_and_renders_each_workspace_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    page = FakePage()

    app = PsyMetriQApplication(page)  # type: ignore[arg-type]

    assert len(app.catalog_records) == 10
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


def test_gui_loads_local_environment_file_without_overriding_process_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    calls: list[tuple[Path, bool]] = []
    monkeypatch.setattr(
        application,
        "load_dotenv",
        lambda path, override: calls.append((path, override)),
    )

    application.main(FakePage())  # type: ignore[arg-type]

    assert calls == [(application.PROJECT_ROOT / ".env", False)]


def test_theme_and_font_size_preferences_apply_and_persist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(application, "SETTINGS_PATH", settings_path)
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]

    asyncio.run(app._toggle_dark_mode(None))
    assert app.dark_mode is True
    assert app.page.theme_mode == application.ft.ThemeMode.DARK
    assert app.page.bgcolor == "#111B19"

    asyncio.run(app._set_font_size(SimpleNamespace(control=SimpleNamespace(value="large"))))

    assert app.font_size == "large"
    assert app.header_title.size > 22
    saved = application.WorkspaceStore(settings_path).load_settings()
    assert saved.theme_mode == "dark"
    assert saved.font_size == "large"

    app._navigate("settings")
    serialized = app._settings_from_controls()
    assert serialized.theme_mode == "dark"
    assert serialized.font_size == "large"

    imported = serialized.model_copy(update={"theme_mode": "light", "font_size": "small"})
    app._apply_settings(imported)
    assert app.dark_mode is False
    assert app.font_size == "small"


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


def test_alpineai_provider_uses_documented_endpoint_and_model_picker_keeps_key_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setenv("ALPINEAI_API_KEY", "do-not-persist-this-key")
    page = FakePage()
    app = PsyMetriQApplication(page)  # type: ignore[arg-type]
    app._navigate("settings")
    app.provider_dropdown.value = "alpineai"
    app._provider_changed(SimpleNamespace(control=app.provider_dropdown))

    assert app.model_field.value == "mistral-large-3-675b-nvfp4"
    assert app.key_environment_field.value == "ALPINEAI_API_KEY"
    assert app.base_url_field.value == "https://api.prod.alpineai.ch/v1"
    assert any(option.key == "alpineai" for option in app.provider_dropdown.options)

    async def fake_list_models(**kwargs: Any) -> list[str]:
        assert kwargs["provider"] == "alpineai"
        assert kwargs["api_key"] == "do-not-persist-this-key"
        return ["model-alpha", "model-beta"]

    monkeypatch.setattr(application, "list_available_models", fake_list_models)
    asyncio.run(app._load_provider_models(None))
    dialog = page.dialogs[-1]
    model_dropdown = dialog.content.controls[1]
    model_dropdown.value = "model-beta"
    choose_button = next(
        action for action in dialog.actions if action.content == "Modell verwenden"
    )
    choose_button.on_click(None)

    assert app.model_field.value == "model-beta"
    assert app.available_models == ["model-alpha", "model-beta"]
    settings = app._settings_from_controls()
    assert "do-not-persist-this-key" not in settings.model_dump_json()

    app.provider_dropdown.value = "openai-compatible"
    app._provider_changed(SimpleNamespace(control=app.provider_dropdown))
    assert app.base_url_field.value == ""


def test_model_discovery_uses_legacy_swissgpt_key_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.delenv("ALPINEAI_API_KEY", raising=False)
    monkeypatch.setenv("SWISSGPT_API_KEY", "legacy-key")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    app._navigate("settings")
    app.provider_dropdown.value = "alpineai"
    observed: dict[str, Any] = {}

    async def fake_list_models(**kwargs: Any) -> list[str]:
        observed.update(kwargs)
        return ["legacy-account-model"]

    monkeypatch.setattr(application, "list_available_models", fake_list_models)
    asyncio.run(app._load_provider_models(None))

    assert observed["api_key"] == "legacy-key"
    assert app.available_models == ["legacy-account-model"]


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


def test_catalogue_filters_limit_versions_by_locale_commercial_and_license_status(
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

    app.commercial_filter = "all"
    license_name = next(
        version.source_documents[0].license_name
        for _family, version in app._visible_versions()
        if version.source_documents
    )
    app.license_filter = license_name.casefold()
    license_matches = app._visible_versions()
    assert license_matches
    assert all(
        any(
            source.license_name.casefold() == license_name.casefold()
            for source in version.source_documents
        )
        for _family, version in license_matches
    )

    source_family, path = app.catalog_records[0]
    undocumented_version = source_family.versions[0].model_copy(
        update={"version_id": "synthetic_undocumented_v1", "source_documents": []}
    )
    app.catalog_records.append(
        (
            source_family.model_copy(
                update={
                    "instrument_id": "synthetic_undocumented",
                    "versions": [undocumented_version],
                }
            ),
            path,
        )
    )
    app.license_filter = "undocumented"
    undocumented = app._visible_versions()
    assert undocumented
    assert all(not version.source_documents for _family, version in undocumented)


def test_language_filter_matches_regional_locale_and_language_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]

    app.language_filter = "de-at"
    regional = app._visible_versions()
    assert regional
    assert all(
        version.locale.casefold() == "de-at"
        for _family, version in regional
    )
    assert any(version.version_id == "gad7_de_at_v1" for _family, version in regional)

    app.language_filter = "de"
    german = app._visible_versions()
    assert german
    assert any(version.locale == "de-AT" for _family, version in german)
    assert any(version.locale == "de-CH" for _family, version in german)


def test_population_filter_uses_broad_source_age_bands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    youth_family = app._find_family("dass_y")
    assert youth_family is not None
    youth_version = youth_family.versions[0]
    assert youth_version.target_populations[0].minimum_age_years == 8
    assert youth_version.target_populations[0].maximum_age_years == 17

    app.population_filter = "children"
    assert any(
        version.version_id == youth_version.version_id
        for _family, version in app._visible_versions()
    )
    app.population_filter = "adolescents"
    assert any(
        version.version_id == youth_version.version_id
        for _family, version in app._visible_versions()
    )
    app.population_filter = "adults"
    assert all(
        version.version_id != youth_version.version_id
        for _family, version in app._visible_versions()
    )

    app.population_filter = "unknown"
    assert any(family.instrument_id == "who5" for family, _version in app._visible_versions())

    app.population_filters = {"children", "adolescents"}
    selected_groups = {
        family.instrument_id
        for family, _version in app._visible_versions()
        if family.instrument_id == "dass_y"
    }
    assert selected_groups == {"dass_y"}
    app.population_filters = {"adults", "older_adults"}
    assert all(
        family.instrument_id != "dass_y" for family, _version in app._visible_versions()
    )


def test_catalogue_layout_bounds_filter_fields_and_version_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]

    catalog_controls = app._catalog_view()
    main_row = catalog_controls[-1]
    left_column = main_row.controls[0]
    version_list = next(
        control for control in left_column.controls if isinstance(control, application.ft.ListView)
    )

    assert app.search_field.width == 360
    assert app.search_field.expand is None
    assert version_list.height == 460
    assert left_column.expand == 5
    assert main_row.controls[1].expand == 6


def test_link_only_wellbeing_records_are_discoverable_and_selectable_as_references(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]

    rosenberg = app._find_family("rosenberg_self_esteem")
    assert rosenberg is not None
    assert len(rosenberg.versions[0].items) == 10
    assert rosenberg.versions[0].source_documents[0].redistribution_permitted is True

    for instrument_id in (
        "who5",
        "wemwbs",
        "general_self_efficacy",
        "perceived_stress_scale",
    ):
        family = app._find_family(instrument_id)
        assert family is not None
        for version in family.versions:
            assert version.item_text_included is False
            assert version.items == []
            card = app._version_card(family, version)
            assert card.content.controls[0].disabled is False
            app.active_version_key = (family.instrument_id, version.version_id)
            details = app._version_detail()
            detail_controls = details.content.controls[1].controls
            source_texts = [
                control.value
                for control in detail_controls
                if isinstance(control, application.ft.Text)
            ]
            source_url = str(version.source_documents[0].source_url)
            assert any(source_url in value for value in source_texts)
            metadata_line = next(value for value in source_texts if value.startswith("ID "))
            assert f"{version.source_reported_item_count} Items laut Quelle" in metadata_line
            source_dimensions = [
                child.value
                for control in detail_controls
                if isinstance(control, application.ft.Column)
                for child in control.controls
                if isinstance(child, application.ft.Text)
            ]
            for dimension in version.source_reported_dimensions:
                assert any(dimension in value for value in source_dimensions)
            item_header = next(
                control
                for control in detail_controls
                if isinstance(control, application.ft.Row)
                and control.controls[0].value == "Itemtext nicht enthalten"
            )
            assert (
                "Metadatenreferenz: Itemtext ist nicht in dieser Software gespeichert"
                in item_header.controls[1].value
            )

            app._toggle_version(family, version, True)
            selection = app._project_selection(family.instrument_id, version.version_id)
            assert selection is not None
            assert selection.item_ids == []
            assert app.status_is_error is False

    app.search_query = "WHO-5"
    assert [family.instrument_id for family, _version in app._visible_versions()] == ["who5"]

    app.search_query = "PSS-4"
    assert [
        version.version_id
        for _family, version in app._visible_versions()
        if _family.instrument_id == "perceived_stress_scale"
    ] == ["pss4_en_v1"]


def test_version_details_expose_instrument_profile_information(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    app.active_version_key = ("phq9", "phq9_en_v1")

    details = app._version_detail()
    def text_values(control: Any) -> list[str]:
        if isinstance(control, application.ft.Text):
            return [control.value]
        children = getattr(control, "controls", None)
        if children is None:
            children = [getattr(control, "content", None)]
        return [value for child in children if child is not None for value in text_values(child)]

    values = text_values(details)

    assert "Instrumentprofil" in values
    assert any(value.startswith("Worum geht es:") for value in values)
    assert any(value.startswith("Erstellungs-/Publikationsjahr: 2001") for value in values)
    assert any(value.startswith("Gütekriterien / COSMIN-Metriken:") for value in values)


def test_catalogue_search_includes_instrument_profile_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    family, path = app.catalog_records[0]
    enriched = family.model_copy(
        update={
            "metadata": family.metadata.model_copy(
                update={"description": "Synthetic searchable profile phrase"}
            )
        }
    )
    app.catalog_records[0] = (enriched, path)
    app.search_query = "searchable profile phrase"

    assert app._visible_versions()


def test_metadata_reference_can_be_included_in_project_and_exported_without_item_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    family = app._find_family("who5")
    assert family is not None
    version = family.versions[0]
    picker = FakeSaveFilePicker()
    app.file_picker = picker  # type: ignore[assignment]

    app._toggle_version(family, version, True)
    app._set_export_format("fhir_json")
    preview = app._export_preview_text()
    asyncio.run(app._export_bundle(None))

    assert "psymetriq-metadata-reference" in preview
    assert '"item_text_included": false' in preview
    assert picker.payload is not None
    with zipfile.ZipFile(io.BytesIO(picker.payload)) as archive:
        reference_name = next(
            name for name in archive.namelist() if name.endswith(".reference.json")
        )
        reference = json.loads(archive.read(reference_name))
        manifest = json.loads(archive.read("manifest.json"))

    assert reference["item_text_included"] is False
    assert reference["version"]["items"] == []
    assert "permission to reproduce" in reference["reference_note"]
    assert manifest["selections"][0]["selection_type"] == "metadata_reference"
    assert manifest["selections"][0]["license_names"]


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


def test_single_item_dimension_is_visible_as_a_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    family = app._find_family("rosenberg_self_esteem")
    assert family is not None
    version = family.versions[0]
    app.active_version_key = (family.instrument_id, version.version_id)

    details = app._version_detail()
    body_controls = details.content.controls[1].controls
    dimension_index = next(
        index
        for index, control in enumerate(body_controls)
        if isinstance(control, application.ft.Text) and control.value == "Itemdimensionen"
    )
    dimension_group = body_controls[dimension_index + 1].controls[0]

    assert dimension_group.controls[0].label == "self_esteem"


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
