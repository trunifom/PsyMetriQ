import json
import logging
import shutil
import traceback
from pathlib import Path

import pytest

from data.generate_mock_data import generate_mock_data
from schemas.questionnaire_schema import (
    QuestionnaireContributor,
    QuestionnaireParent,
    QuestionnaireVersionReference,
    TargetPopulation,
)
from src.core.search_engine import QuestionnaireDataError, QuestionnaireSearchEngine


@pytest.fixture
def generated_data_directory(tmp_path: Path) -> Path:
    """Create the synthetic questionnaire files in an isolated test directory."""
    generate_mock_data(tmp_path)
    return tmp_path


def test_search_matches_instruments_dimensions_and_items(
    generated_data_directory: Path,
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_data_directory)

    instrument_matches = search_engine.search_items("ASRS")
    dimension_matches = search_engine.search_items("ORGANI")
    item_matches = search_engine.search_items("lose track")

    assert any(match.match_type == "instrument" for match in instrument_matches)
    assert any(
        match.match_type == "dimension" and match.dimension == "organization"
        for match in dimension_matches
    )
    assert any(
        match.match_type == "item" and match.item_id == "asrs_demo_01"
        for match in item_matches
    )


def test_search_matches_response_labels_case_insensitively(
    generated_data_directory: Path,
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_data_directory)

    matches = search_engine.search_items("VERY OFTEN")

    assert len(matches) == 3
    assert all(match.match_type == "item" for match in matches)
    assert all("response_options" in match.matched_fields for match in matches)


def test_blank_and_missing_search_terms_return_no_results(
    generated_data_directory: Path,
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_data_directory)

    assert search_engine.search_items("  ") == []
    assert search_engine.search_items("not present anywhere") == []


def test_reload_adds_files_and_preserves_last_valid_data_on_invalid_file(
    generated_data_directory: Path, caplog: pytest.LogCaptureFixture
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_data_directory)
    added_data = generate_mock_data(generated_data_directory / "new_team_folder")
    added_file = generated_data_directory / "new_instrument.json"
    questionnaire_json = added_data[0].read_text(encoding="utf-8")
    added_file.write_text(
        questionnaire_json.replace("bdi_ii_demo", "shared_bdi_demo"), encoding="utf-8"
    )

    assert search_engine.reload() == 3
    assert search_engine.search_items("shared_bdi_demo")

    (generated_data_directory / "broken.json").write_text("{invalid", encoding="utf-8")
    with caplog.at_level(logging.ERROR), pytest.raises(QuestionnaireDataError):
        search_engine.reload()

    assert "Could not validate questionnaire file broken.json" in caplog.text
    assert search_engine.search_items("shared_bdi_demo")


def test_duplicate_instrument_ids_are_rejected(
    generated_data_directory: Path, caplog: pytest.LogCaptureFixture
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_data_directory)
    shutil.copyfile(
        generated_data_directory / "bdi_ii_demo.json",
        generated_data_directory / "duplicate.json",
    )

    with caplog.at_level(logging.ERROR), pytest.raises(
        QuestionnaireDataError, match="Duplicate instrument_id"
    ):
        search_engine.reload()

    assert "Duplicate instrument_id" in caplog.text
    assert search_engine.search_items("bdi_ii_demo")


def test_invalid_questionnaire_values_are_not_written_to_logs(
    generated_data_directory: Path, caplog: pytest.LogCaptureFixture
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_data_directory)
    questionnaire_path = generated_data_directory / "bdi_ii_demo.json"
    questionnaire_data = json.loads(questionnaire_path.read_text(encoding="utf-8"))
    questionnaire_data["versions"][0]["items"][0]["variable_name"] = "invalid name"
    questionnaire_data["versions"][0]["items"][0]["prompt_text"] = "PRIVATE-ITEM-TEXT"
    questionnaire_path.write_text(json.dumps(questionnaire_data), encoding="utf-8")

    with caplog.at_level(logging.ERROR), pytest.raises(QuestionnaireDataError) as error_info:
        search_engine.reload()

    assert "Could not validate questionnaire file bdi_ii_demo.json" in caplog.text
    assert "PRIVATE-ITEM-TEXT" not in caplog.text
    assert "PRIVATE-ITEM-TEXT" not in "".join(traceback.format_exception(error_info.value))


def test_missing_data_directory_is_a_supported_empty_state(tmp_path: Path) -> None:
    data_directory = tmp_path / "not-created-yet"
    search_engine = QuestionnaireSearchEngine(data_directory)

    assert search_engine.search_items("anything") == []
    assert search_engine.reload() == 0


def test_search_matches_variant_metadata_and_returns_version_details(
    generated_data_directory: Path,
) -> None:
    questionnaire_path = generated_data_directory / "bdi_ii_demo.json"
    questionnaire = QuestionnaireParent.model_validate_json(
        questionnaire_path.read_text(encoding="utf-8")
    )
    base_version = questionnaire.versions[0]
    adapted_version = base_version.model_copy(
        update={
            "display_name": "German Adolescent Short Form",
            "language": "de",
            "locale": "de-DE",
            "form_type": "short",
            "variant_types": ["translation", "cultural_adaptation", "population_adaptation"],
            "target_populations": [
                TargetPopulation(
                    group_name="adolescents", minimum_age_years=13, maximum_age_years=17
                )
            ],
            "contributors": [
                QuestionnaireContributor(
                    name="Synthetic Translation Team", role="translator"
                )
            ],
            "based_on": [
                QuestionnaireVersionReference(
                    instrument_id="source_instrument", version_id="source_v1"
                )
            ],
        }
    )
    adapted_questionnaire = questionnaire.model_copy(
        update={"versions": [adapted_version]}
    )
    questionnaire_path.write_text(adapted_questionnaire.model_dump_json(), encoding="utf-8")
    search_engine = QuestionnaireSearchEngine(generated_data_directory)

    locale_results = search_engine.search_items("de-DE")
    form_results = search_engine.search_items("short")
    audience_results = search_engine.search_items("adolescents")
    contributor_results = search_engine.search_items("Translation Team")

    assert locale_results[0].locale == "de-DE"
    assert form_results[0].form_type == "short"
    assert audience_results[0].target_populations[0].group_name == "adolescents"
    assert contributor_results[0].version_contributors[0].name == "Synthetic Translation Team"
    assert contributor_results[0].based_on[0].instrument_id == "source_instrument"
