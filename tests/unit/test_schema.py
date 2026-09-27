import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from data.generate_mock_data import generate_mock_data
from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireContributor,
    QuestionnaireParent,
    QuestionnaireVersion,
    QuestionnaireVersionReference,
    ResponseOption,
    ScoringAlgorithm,
    TargetPopulation,
)


def make_item(
    variable_name: str = "demo_item",
    item_id: str = "demo_01",
    response_set_ref: str = "frequency_5",
) -> ItemSchema:
    """Return a valid synthetic item with configurable reference fields."""
    return ItemSchema(
        item_id=item_id,
        variable_name=variable_name,
        dimension="wellbeing",
        prompt_text="A synthetic example question.",
        response_set_ref=response_set_ref,
    )


def make_version() -> QuestionnaireVersion:
    """Return a valid version used as the baseline for schema tests."""
    return QuestionnaireVersion(
        version_id="demo_v1",
        language="en",
        response_sets={
            "frequency_5": [
                ResponseOption(code=0, label="Never", score=0),
                ResponseOption(code=1, label="Often", score=1),
            ]
        },
        items=[make_item()],
        scoring_algorithms=[
            ScoringAlgorithm(
                output_variable="demo_total",
                method="sum",
                target_items=["demo_01"],
            )
        ],
    )


def test_variable_name_accepts_the_26_character_limit() -> None:
    assert len(make_item("a" + "b" * 25).variable_name) == 26


@pytest.mark.parametrize(
    "invalid_name",
    ["has space", "1starts_with_number", "has-hyphen", "a" * 27, ""],
)
def test_variable_name_rejects_invalid_redcap_names(invalid_name: str) -> None:
    with pytest.raises(ValidationError):
        make_item(invalid_name)


def test_questionnaire_version_rejects_duplicate_item_ids() -> None:
    version = make_version()
    with pytest.raises(ValidationError, match="item_id values must be unique"):
        QuestionnaireVersion(
            version_id=version.version_id,
            language=version.language,
            response_sets=version.response_sets,
            items=[make_item(), make_item(variable_name="second_item")],
        )


@pytest.mark.parametrize(
    ("response_sets", "items"),
    [
        ({}, [make_item()]),
        ({"frequency_5": [ResponseOption(code=0, label="Never", score=0)]}, []),
    ],
)
def test_questionnaire_version_requires_items_and_response_sets(
    response_sets: dict[str, list[ResponseOption]], items: list[ItemSchema]
) -> None:
    with pytest.raises(ValidationError):
        QuestionnaireVersion(
            version_id="incomplete_version",
            language="en",
            response_sets=response_sets,
            items=items,
        )


def test_questionnaire_version_rejects_case_insensitive_variable_collisions() -> None:
    version = make_version()
    with pytest.raises(ValidationError, match="variable_name values must be unique"):
        QuestionnaireVersion(
            version_id=version.version_id,
            language=version.language,
            response_sets=version.response_sets,
            items=[make_item(), make_item("DEMO_ITEM", item_id="demo_02")],
        )


def test_questionnaire_version_rejects_unknown_item_response_set() -> None:
    version = make_version()
    with pytest.raises(ValidationError, match="unknown response set"):
        QuestionnaireVersion(
            version_id=version.version_id,
            language=version.language,
            response_sets=version.response_sets,
            items=[make_item(response_set_ref="missing_set")],
        )


def test_questionnaire_version_rejects_unknown_scoring_item() -> None:
    version = make_version()

    with pytest.raises(ValidationError, match="unknown items"):
        QuestionnaireVersion(
            version_id=version.version_id,
            language=version.language,
            response_sets=version.response_sets,
            items=version.items,
            scoring_algorithms=[
                ScoringAlgorithm(
                    output_variable="demo_total",
                    method="sum",
                    target_items=["missing"],
                )
            ],
        )


def test_parent_accepts_a_valid_questionnaire_version() -> None:
    parent = QuestionnaireParent(
        instrument_id="demo_instrument",
        name_full="Synthetic Demonstration Questionnaire",
        is_commercial=False,
        versions=[make_version()],
    )

    assert parent.versions[0].items[0].item_id == "demo_01"


def test_questionnaire_parent_rejects_duplicate_version_ids() -> None:
    version = make_version()
    with pytest.raises(ValidationError, match="version_id values must be unique"):
        QuestionnaireParent(
            instrument_id="demo_instrument",
            name_full="Synthetic Demonstration Questionnaire",
            is_commercial=False,
            versions=[version, version],
        )


def test_parent_json_round_trip_preserves_validated_schema() -> None:
    parent = QuestionnaireParent(
        instrument_id="demo_instrument",
        name_full="Synthetic Demonstration Questionnaire",
        is_commercial=False,
        versions=[make_version()],
    )

    restored_parent = QuestionnaireParent.model_validate_json(parent.model_dump_json())
    assert restored_parent == parent


def test_questionnaire_supports_authored_translated_short_population_variant() -> None:
    original_version = make_version()
    localized_short_form = QuestionnaireVersion(
        version_id="demo_de_adolescent_short",
        language="de",
        display_name="German Adolescent Short Form",
        locale="de-DE",
        form_type="short",
        variant_types=["translation", "cultural_adaptation", "population_adaptation"],
        target_populations=[
            TargetPopulation(
                group_name="adolescents",
                minimum_age_years=13,
                maximum_age_years=17,
            )
        ],
        contributors=[
            QuestionnaireContributor(
                name="Synthetic Translation Team",
                role="translator",
                affiliation="Demonstration Institute",
            )
        ],
        based_on=[
            QuestionnaireVersionReference(
                instrument_id="demo_instrument",
                version_id=original_version.version_id,
            )
        ],
        publication_year=2024,
        source_citation="Synthetic example citation for schema testing.",
        response_sets=original_version.response_sets,
        items=[
            make_item(
                variable_name="localized_item",
                item_id="localized_01",
            )
        ],
    )
    parent = QuestionnaireParent(
        instrument_id="demo_instrument",
        name_full="Synthetic Demonstration Questionnaire",
        is_commercial=False,
        contributors=[QuestionnaireContributor(name="Synthetic Original Author", role="author")],
        versions=[original_version, localized_short_form],
    )

    restored = QuestionnaireParent.model_validate_json(parent.model_dump_json())
    restored_variant = restored.versions[1]
    assert restored_variant.form_type == "short"
    assert restored_variant.locale == "de-DE"
    assert restored_variant.target_populations[0].maximum_age_years == 17
    assert restored_variant.contributors[0].role == "translator"
    assert restored_variant.based_on[0].version_id == "demo_v1"


@pytest.mark.parametrize(
    "language_tag",
    ["de", "en-US", "zh-Hans-CN", "en-u-ca-gregory"],
)
def test_questionnaire_version_accepts_common_bcp47_language_tags(
    language_tag: str,
) -> None:
    version = make_version()

    localized_version = QuestionnaireVersion(
        version_id="localized_version",
        language=language_tag,
        response_sets=version.response_sets,
        items=version.items,
    )

    assert localized_version.language == language_tag


@pytest.mark.parametrize("invalid_tag", ["de_DE", "123", "en--US", "e"])
def test_questionnaire_version_rejects_malformed_language_and_locale_tags(
    invalid_tag: str,
) -> None:
    version = make_version()

    with pytest.raises(ValidationError, match="BCP 47"):
        QuestionnaireVersion(
            version_id="invalid_locale",
            language=version.language,
            locale=invalid_tag,
            response_sets=version.response_sets,
            items=version.items,
        )


def test_target_population_rejects_reversed_age_range() -> None:
    with pytest.raises(ValidationError, match="minimum_age_years cannot exceed"):
        TargetPopulation(
            group_name="adolescents",
            minimum_age_years=18,
            maximum_age_years=12,
        )


def test_questionnaire_parent_rejects_unknown_local_version_reference() -> None:
    derived_version = make_version().model_copy(
        update={
            "based_on": [
                QuestionnaireVersionReference(
                    instrument_id="demo_instrument", version_id="missing_version"
                )
            ]
        }
    )

    with pytest.raises(ValidationError, match="unknown local version"):
        QuestionnaireParent(
            instrument_id="demo_instrument",
            name_full="Synthetic Demonstration Questionnaire",
            is_commercial=False,
            versions=[derived_version],
        )


def test_questionnaire_parent_rejects_cyclic_version_lineage() -> None:
    first_version = make_version().model_copy(
        update={
            "based_on": [
                QuestionnaireVersionReference(
                    instrument_id="demo_instrument", version_id="demo_v2"
                )
            ]
        }
    )
    second_version = make_version().model_copy(
        update={
            "version_id": "demo_v2",
            "based_on": [
                QuestionnaireVersionReference(
                    instrument_id="demo_instrument", version_id="demo_v1"
                )
            ],
        }
    )

    with pytest.raises(ValidationError, match="lineage cannot contain cycles"):
        QuestionnaireParent(
            instrument_id="demo_instrument",
            name_full="Synthetic Demonstration Questionnaire",
            is_commercial=False,
            versions=[first_version, second_version],
        )


def test_questionnaire_parent_allows_external_source_version_reference() -> None:
    translated_version = make_version().model_copy(
        update={
            "based_on": [
                QuestionnaireVersionReference(
                    instrument_id="external_instrument", version_id="source_v1"
                )
            ]
        }
    )

    parent = QuestionnaireParent(
        instrument_id="demo_instrument",
        name_full="Synthetic Demonstration Questionnaire",
        is_commercial=False,
        versions=[translated_version],
    )

    assert parent.versions[0].based_on[0].instrument_id == "external_instrument"


def test_mock_generator_writes_two_validated_synthetic_files(tmp_path: Path) -> None:
    generated_paths = generate_mock_data(tmp_path)

    assert {path.name for path in generated_paths} == {
        "bdi_ii_demo.json",
        "asrs_demo.json",
    }
    assert all(
        QuestionnaireParent.model_validate_json(path.read_text("utf-8"))
        for path in generated_paths
    )


def test_mock_generator_logs_and_raises_on_output_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocked_directory = tmp_path / "existing_file"
    blocked_directory.write_text("not a directory", encoding="utf-8")

    with caplog.at_level(logging.ERROR), pytest.raises(OSError):
        generate_mock_data(blocked_directory / "child")

    assert "Could not write synthetic questionnaire data" in caplog.text
