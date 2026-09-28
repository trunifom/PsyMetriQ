import csv
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from data.generate_mock_data import generate_mock_data
from schemas.questionnaire_schema import QuestionnaireParent
from src.exporters.data_exchange import (
    DataExchangeError,
    export_fhir_questionnaire,
    export_item_csv,
    export_psymetriq_json,
    export_questionnaire,
    export_redcap_data_dictionary,
    import_fhir_questionnaire,
    import_psymetriq_json,
    import_redcap_data_dictionary,
    select_questionnaire_items,
)


@pytest.fixture
def synthetic_questionnaire(tmp_path: Path) -> QuestionnaireParent:
    generated_paths = generate_mock_data(tmp_path)
    return QuestionnaireParent.model_validate_json(
        generated_paths[0].read_text(encoding="utf-8")
    )


def test_psymetriq_json_export_import_round_trip(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    serialized = export_psymetriq_json([synthetic_questionnaire])

    imported = import_psymetriq_json(serialized)

    assert imported == [synthetic_questionnaire]


def test_fhir_questionnaire_preserves_family_version_items_and_scales(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]

    exported = export_fhir_questionnaire(synthetic_questionnaire, version)
    imported = import_fhir_questionnaire(exported)

    assert imported.instrument_id == synthetic_questionnaire.instrument_id
    assert imported.name_full == synthetic_questionnaire.name_full
    assert imported.versions[0].version_id == version.version_id
    assert imported.versions[0].language == version.language
    assert [item.prompt_text for item in imported.versions[0].items] == [
        item.prompt_text for item in version.items
    ]
    first_item = imported.versions[0].items[0]
    original_item = version.items[0]
    assert imported.versions[0].response_sets[first_item.response_set_ref] == version.response_sets[
        original_item.response_set_ref
    ]


def test_redcap_dictionary_preserves_fields_without_inventing_scores(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    redcap_csv = export_redcap_data_dictionary(synthetic_questionnaire, version)

    imported = import_redcap_data_dictionary(redcap_csv, language=version.language)

    assert imported.is_commercial is None
    assert imported.versions[0].language == version.language
    assert [item.prompt_text for item in imported.versions[0].items] == [
        item.prompt_text for item in version.items
    ]
    original_options = version.response_sets[version.items[0].response_set_ref]
    imported_options = imported.versions[0].response_sets[
        imported.versions[0].items[0].response_set_ref
    ]
    assert [option.label for option in imported_options] == [
        option.label for option in original_options
    ]
    assert all(option.score is None for option in imported_options)


def test_item_csv_uses_standard_quoting_for_multiline_or_comma_text(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    csv_text = export_item_csv(synthetic_questionnaire, version)
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(rows) == len(version.items)
    assert rows[0]["instrument_id"] == synthetic_questionnaire.instrument_id
    assert rows[0]["prompt_text"] == version.items[0].prompt_text
    assert json.loads(rows[0]["response_options"])


def test_xlsx_export_contains_items_responses_scoring_and_sources(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]

    extension, workbook_bytes = export_questionnaire(family, version.version_id, "xlsx")
    workbook = load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=True)

    assert extension == ".xlsx"
    assert workbook.sheetnames == ["Items", "Antwortoptionen", "Scoring", "Quellen"]
    rows = list(workbook["Items"].values)
    headers = list(rows[0])
    first_item = dict(zip(headers, rows[1], strict=True))
    assert first_item["Item ID"] == version.items[0].item_id
    assert first_item["Itemtext"] == version.items[0].prompt_text
    assert list(workbook["Antwortoptionen"].values)[1][2] == next(
        iter(version.response_sets.values())
    )[0].label
    workbook.close()


def test_xlsx_keeps_formula_like_item_text_as_literal_string(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]
    formula_like = version.items[0].model_copy(update={"prompt_text": "=1+1"})
    version = version.model_copy(update={"items": [formula_like, *version.items[1:]]})
    family = family.model_copy(update={"versions": [version]})

    _extension, workbook_bytes = export_questionnaire(family, version.version_id, "xlsx")
    workbook = load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=False)
    item_row = list(workbook["Items"].values)[1]

    assert item_row[9] == "=1+1"
    assert workbook["Items"]["J2"].data_type == "s"
    workbook.close()


def test_required_items_round_trip_through_fhir_and_redcap(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]
    required_item = version.items[0].model_copy(update={"is_required": True})
    version = version.model_copy(update={"items": [required_item, *version.items[1:]]})
    family = family.model_copy(update={"versions": [version]})

    fhir_resource = export_fhir_questionnaire(family, version)
    imported_fhir = import_fhir_questionnaire(fhir_resource)
    redcap_csv = export_redcap_data_dictionary(family, version)
    imported_redcap = import_redcap_data_dictionary(redcap_csv, language=version.language)

    assert fhir_resource["item"][0]["required"] is True
    assert imported_fhir.versions[0].items[0].is_required is True
    assert imported_redcap.versions[0].items[0].is_required is True


def test_requiredness_survives_fhir_and_redcap_round_trips(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]
    required_item = version.items[0].model_copy(update={"is_required": True})
    version = version.model_copy(
        update={"items": [required_item, *version.items[1:]]}
    )
    family = family.model_copy(update={"versions": [version]})

    fhir = export_fhir_questionnaire(family, version)
    imported_fhir = import_fhir_questionnaire(fhir)
    redcap = export_redcap_data_dictionary(family, version)
    imported_redcap = import_redcap_data_dictionary(redcap, language=version.language)

    assert fhir["item"][0]["required"] is True
    assert imported_fhir.versions[0].items[0].is_required is True
    assert imported_redcap.versions[0].items[0].is_required is True


def test_psymetriq_json_rejects_duplicate_instrument_ids(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    with pytest.raises(DataExchangeError, match="duplicate instrument_id"):
        import_psymetriq_json(
            json.dumps([synthetic_questionnaire.model_dump(mode="json")] * 2)
        )


def test_redcap_import_requires_expected_dictionary_headers() -> None:
    with pytest.raises(DataExchangeError, match="missing required"):
        import_redcap_data_dictionary("a,b\n1,2\n", language="en")


def test_export_rejects_unknown_version(synthetic_questionnaire: QuestionnaireParent) -> None:
    with pytest.raises(DataExchangeError, match="Unknown questionnaire version"):
        from src.exporters.data_exchange import export_questionnaire

        export_questionnaire(synthetic_questionnaire, "missing", "fhir_json")


def test_item_subset_keeps_valid_scoring_only_when_all_targets_are_selected(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    selected = select_questionnaire_items(
        synthetic_questionnaire,
        version.version_id,
        [version.items[0].item_id],
    )

    assert len(selected.versions[0].items) == 1
    assert selected.versions[0].response_sets.keys() == {
        version.items[0].response_set_ref
    }
    assert selected.versions[0].scoring_algorithms == []


def test_item_subset_rejects_unknown_saved_references(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    with pytest.raises(DataExchangeError, match="unknown item IDs"):
        select_questionnaire_items(
            synthetic_questionnaire,
            synthetic_questionnaire.versions[0].version_id,
            ["missing_item"],
        )


def test_study_adaptation_changes_only_derived_export_and_drops_affected_scores(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    original_prompt = version.items[0].prompt_text
    adapted = select_questionnaire_items(
        synthetic_questionnaire,
        version.version_id,
        [],
        {version.items[0].item_id: ("Study-specific wording", "Clarified the study timeframe")},
    )

    assert synthetic_questionnaire.versions[0].items[0].prompt_text == original_prompt
    assert adapted.versions[0].items[0].prompt_text == "Study-specific wording"
    assert "not been psychometrically validated" in adapted.versions[0].items[0].metadata.notes
    assert adapted.versions[0].scoring_algorithms == []
