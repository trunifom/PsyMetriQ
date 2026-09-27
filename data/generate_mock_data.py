import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (  # noqa: E402, I001
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
    ScoringAlgorithm,
)


OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "02_extracted_jsons"
LOGGER = logging.getLogger(__name__)


def build_demo_questionnaire(
    instrument_id: str,
    name_full: str,
    version_id: str,
    item_specs: list[tuple[str, str, str, str]],
    response_set_name: str,
    response_options: list[ResponseOption],
) -> QuestionnaireParent:
    """Build a validated questionnaire from synthetic item specifications.

    Each specification contains an item ID, REDCap variable name, dimension,
    and fabricated prompt. This helper deliberately uses no licensed item text.
    """
    items = [
        ItemSchema(
            item_id=item_id,
            variable_name=variable_name,
            dimension=dimension,
            prompt_text=prompt_text,
            response_set_ref=response_set_name,
            redcap_field_type="radio",
        )
        for item_id, variable_name, dimension, prompt_text in item_specs
    ]
    version = QuestionnaireVersion(
        version_id=version_id,
        language="en",
        cosmin_metrics={"demo_data": True},
        response_sets={response_set_name: response_options},
        items=items,
        scoring_algorithms=[
            ScoringAlgorithm(
                output_variable=f"{instrument_id}_total",
                method="sum",
                target_items=[item.item_id for item in items],
                missing_data_rules="Demo only: calculate when all demo items are answered.",
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id=instrument_id,
        name_full=name_full,
        construct_ontology=[],
        is_commercial=False,
        versions=[version],
    )


def generate_mock_data(output_directory: Path = OUTPUT_DIRECTORY) -> list[Path]:
    """Write two deterministic, validated synthetic examples to the data folder.

    These fixtures are for development only and are not validated clinical
    instruments. Filesystem failures are logged and re-raised for callers.
    """
    frequency_options = [
        ResponseOption(code=0, label="Not at all", score=0),
        ResponseOption(code=1, label="A little", score=1),
        ResponseOption(code=2, label="Moderately", score=2),
        ResponseOption(code=3, label="A lot", score=3),
    ]
    asrs_options = [
        ResponseOption(code=0, label="Never", score=0),
        ResponseOption(code=1, label="Rarely", score=1),
        ResponseOption(code=2, label="Sometimes", score=2),
        ResponseOption(code=3, label="Often", score=3),
        ResponseOption(code=4, label="Very often", score=4),
    ]

    questionnaires = [
        (
            "bdi_ii_demo",
            build_demo_questionnaire(
                instrument_id="bdi_ii_demo",
                name_full="BDI-II Inspired Synthetic Demonstration",
                version_id="demo_v1",
                item_specs=[
                    (
                        "bdi_demo_01",
                        "bdi_demo_01",
                        "mood",
                        "During the past two weeks, how often have you felt low in mood?",
                    ),
                    (
                        "bdi_demo_02",
                        "bdi_demo_02",
                        "energy",
                        "During the past two weeks, how often has your usual activity felt tiring?",
                    ),
                    (
                        "bdi_demo_03",
                        "bdi_demo_03",
                        "interest",
                        "During the past two weeks, how often have you had less interest "
                        "in hobbies?",
                    ),
                ],
                response_set_name="impact_4",
                response_options=frequency_options,
            ),
        ),
        (
            "asrs_demo",
            build_demo_questionnaire(
                instrument_id="asrs_demo",
                name_full="ASRS-Inspired Synthetic Demonstration",
                version_id="demo_v1",
                item_specs=[
                    (
                        "asrs_demo_01",
                        "asrs_demo_01",
                        "attention",
                        "How often do you lose track of a task while working through its steps?",
                    ),
                    (
                        "asrs_demo_02",
                        "asrs_demo_02",
                        "organization",
                        "How often do you find it difficult to organize several routine tasks?",
                    ),
                    (
                        "asrs_demo_03",
                        "asrs_demo_03",
                        "restlessness",
                        "How often do you feel restless when you need to remain seated?",
                    ),
                ],
                response_set_name="frequency_5",
                response_options=asrs_options,
            ),
        ),
    ]

    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        output_paths: list[Path] = []
        for filename, questionnaire in questionnaires:
            output_path = output_directory / f"{filename}.json"
            output_path.write_text(
                json.dumps(
                    questionnaire.model_dump(mode="json"), indent=2, ensure_ascii=False
                )
                + "\n",
                encoding="utf-8",
            )
            output_paths.append(output_path)
        return output_paths
    except OSError:
        LOGGER.exception("Could not write synthetic questionnaire data to %s", output_directory)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        generated_paths = generate_mock_data()
    except OSError:
        # The generator already logged this filesystem failure with its path.
        sys.exit(1)
    except ValueError:
        LOGGER.exception("Synthetic questionnaire generation failed")
        sys.exit(1)
    for generated_path in generated_paths:
        LOGGER.info("Generated %s", generated_path.relative_to(PROJECT_ROOT))