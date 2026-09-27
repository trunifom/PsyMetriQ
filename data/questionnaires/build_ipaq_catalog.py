"""Build permission-cleared IPAQ short-form test records from official PDFs.

The International Physical Activity Questionnaire site publishes its forms
under CC BY 4.0, permitting redistribution with attribution. Its download page
warns that independently submitted translations are supplied as-is and their
accuracy is not checked. Accordingly, the German form below is identified as
an official-site translation, not certified as psychometrically equivalent.
"""

import hashlib
import json
import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (  # noqa: E402, I001
    ItemSchema,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    QuestionnaireVersionReference,
    TargetPopulation,
)

LOGGER = logging.getLogger(__name__)
PDF_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "forms"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"
IPAQ_DOWNLOAD_URL = "https://sites.google.com/view/ipaq/download"
IPAQ_FAQ_URL = "https://sites.google.com/view/ipaq/faq"
IPAQ_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
IPAQ_LICENSE_NOTICE = (
    "The official IPAQ FAQ states that IPAQ is available under CC BY 4.0, allowing "
    "redistribution and adaptation with attribution, a license link, and notice of changes. "
    "The bundled PDF is unchanged; its JSON record represents each days/hours/minutes blank "
    "as a separate numeric response field."
)


def _numeric_item(
    *,
    item_id: str,
    variable_name: str,
    dimension: str,
    prompt_text: str,
    unit: str,
    maximum: float,
    source_question: str,
) -> ItemSchema:
    """Create one numeric answer component with an explicit unit and range."""
    return ItemSchema(
        item_id=item_id,
        variable_name=variable_name,
        dimension=dimension,
        prompt_text=prompt_text,
        response_mode="numeric",
        response_set_ref=None,
        measurement_unit=unit,
        numeric_minimum=0,
        numeric_maximum=maximum,
        redcap_field_type="text",
        metadata=QuestionnaireMetadata(
            keywords=["physical activity", dimension.replace("_", " ")],
            characteristics=["self-report", "numeric-entry", source_question],
        ),
    )


def _duration_group(
    prefix: str,
    question_number: int,
    dimension: str,
    source_prompt: str,
    *,
    duration_prompt: str | None = None,
    duration_question_number: int | None = None,
    duration_period: str = "active-day",
    includes_days: bool = True,
    days_prompt: str | None = None,
) -> list[ItemSchema]:
    """Split a source form's day/hour/minute blanks into typed response fields."""
    items: list[ItemSchema] = []
    if includes_days:
        items.append(
            _numeric_item(
                item_id=f"{prefix}_{dimension}_days",
                variable_name=f"{prefix}_{dimension[:8]}_days",
                dimension=dimension,
                prompt_text=days_prompt or source_prompt,
                unit="days/week",
                maximum=7,
                source_question=f"source-question-{question_number}",
            )
        )
    items.extend(
        [
            _numeric_item(
                item_id=f"{prefix}_{dimension}_hours",
                variable_name=f"{prefix}_{dimension[:7]}_hr",
                dimension=dimension,
                prompt_text=duration_prompt or source_prompt,
                unit=f"hours/{duration_period}",
                maximum=24,
                source_question=f"source-question-{duration_question_number or question_number}",
            ),
            _numeric_item(
                item_id=f"{prefix}_{dimension}_minutes",
                variable_name=f"{prefix}_{dimension[:6]}_min",
                dimension=dimension,
                prompt_text=duration_prompt or source_prompt,
                unit=f"minutes/{duration_period}",
                maximum=59,
                source_question=f"source-question-{duration_question_number or question_number}",
            ),
        ]
    )
    return items


def _short_form_items(prefix: str, language: str, *, elderly: bool = False) -> list[ItemSchema]:
    """Transcribe IPAQ short-form blanks without flattening numeric units."""
    if elderly:
        prompts = {
            "sitting": (
                "During the last 7 days, how much time did you spend sitting during a day?"
            ),
            "walking": (
                "During the last 7 days, on how many days did you walk for at least 10 minutes "
                "at a time? How much time did you usually spend walking on one of those days?"
            ),
            "moderate": (
                "During the last 7 days, on how many days did you do moderate physical activities "
                "like gardening, cleaning, bicycling at a regular pace, swimming or other fitness "
                "activities? Think only about activities done for at least 10 minutes at a time. "
                "Do not include walking."
            ),
            "vigorous": (
                "During the last 7 days, on how many days did you do vigorous physical activities "
                "like heavy lifting, heavier garden or construction work, chopping woods, "
                "aerobics, "
                "jogging/running or fast bicycling? Think only about activities done for at least "
                "10 minutes at a time."
            ),
        }
        return [
            *_duration_group(
                prefix,
                1,
                "sitting_weekday",
                prompts["sitting"],
                duration_period="day",
                includes_days=False,
            ),
            *_duration_group(prefix, 2, "walking", prompts["walking"]),
            *_duration_group(prefix, 3, "moderate", prompts["moderate"]),
            *_duration_group(prefix, 4, "vigorous", prompts["vigorous"]),
        ]

    if language == "en":
        vigorous_prompt = (
            "During the last 7 days, on how many days did you do vigorous physical activities "
            "like heavy lifting, digging, aerobics, or fast bicycling?"
        )
        vigorous_duration_prompt = (
            "How much time did you usually spend doing vigorous physical activities on one "
            "of those days?"
        )
        moderate_prompt = (
            "During the last 7 days, on how many days did you do moderate physical activities "
            "like carrying light loads, bicycling at a regular pace, or doubles tennis? Do not "
            "include walking."
        )
        moderate_duration_prompt = (
            "How much time did you usually spend doing moderate physical activities on one "
            "of those days?"
        )
        walking_prompt = (
            "During the last 7 days, on how many days did you walk for at least 10 minutes "
            "at a time?"
        )
        walking_duration_prompt = (
            "How much time did you usually spend walking on one of those days?"
        )
        sitting_prompt = (
            "During the last 7 days, how much time did you spend sitting on a week day?"
        )
    else:
        vigorous_prompt = (
            "Denken sie nur an die körperlichen Aktivitäten die Sie für mindestens 10 Minuten "
            "ohne Unterbrechung verrichtet haben. An wie vielen der vergangenen 7 Tage haben "
            "Sie anstrengende körperliche Aktivitäten wie Aerobic, Laufen, schnelles "
            "Fahrradfahren oder schnelles Schwimmen verrichtet?"
        )
        vigorous_duration_prompt = (
            "Wie viel Zeit haben Sie für gewöhnlich an einem dieser Tage mit anstrengender "
            "körperlicher Aktivität verbracht?"
        )
        moderate_prompt = (
            "Denken Sie erneut nur an die körperlichen Aktivitäten die Sie für mindestens "
            "10 Minuten ohne Unterbrechung verrichtet haben. An wie vielen der vergangenen "
            "7 Tage haben sie moderate körperliche Aktivitäten, wie das Tragen leichter Lasten, "
            "Fahrradfahren bei gewöhnlicher Geschwindigkeit oder Schwimmen bei gewöhnlicher "
            "Geschwindigkeit verrichtet? Hierzu zählt nicht zu Fuß gehen."
        )
        moderate_duration_prompt = (
            "Wie viel Zeit haben Sie für gewöhnlich an einem dieser Tage mit moderater "
            "körperlicher Aktivität verbracht?"
        )
        walking_prompt = (
            "An wie vielen der vergangenen 7 Tage sind Sie mindestens 10 Minuten ohne "
            "Unterbrechung zu Fuß gegangen? Dieses beinhaltet Gehstrecken daheim oder in der "
            "Arbeit, gehen um von einem Ort zu einem anderen zu gelangen, sowie alles andere "
            "Gehen zur Erholung, Bewegung oder Freizeit."
        )
        walking_duration_prompt = (
            "Wie viel Zeit haben Sie für gewöhnlich an einem dieser Tage mit Gehen verbracht?"
        )
        sitting_prompt = (
            "Wie viel Zeit haben Sie in den vergangenen 7 Tagen an einem Wochentag mit Sitzen "
            "verbracht? Dies kann Zeit beinhalten wie Sitzen am Schreibtisch, Besuchen von "
            "Freunden, vor dem Fernseher sitzen oder liegen und auch sitzen in einem "
            "öffentlichen Verkehrsmittel."
        )
    return [
        *_duration_group(
            prefix,
            1,
            "vigorous",
            vigorous_prompt,
            duration_prompt=vigorous_duration_prompt,
            duration_question_number=2,
        ),
        *_duration_group(
            prefix,
            3,
            "moderate",
            moderate_prompt,
            duration_prompt=moderate_duration_prompt,
            duration_question_number=4,
        ),
        *_duration_group(
            prefix,
            5,
            "walking",
            walking_prompt,
            duration_prompt=walking_duration_prompt,
            duration_question_number=6,
        ),
        *_duration_group(
            prefix,
            7,
            "sitting_weekday",
            sitting_prompt,
            duration_period="weekday",
            includes_days=False,
        ),
    ]


def _source_document(
    *,
    title: str,
    language: str,
    source_url: str,
    pdf_filename: str,
) -> QuestionnaireSourceDocument:
    """Create CC BY 4.0 provenance and a SHA-256 digest for the exact official form."""
    pdf_path = PDF_DIRECTORY / pdf_filename
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Required official IPAQ form is missing: {pdf_path}")
    return QuestionnaireSourceDocument(
        title=title,
        document_type="questionnaire_form",
        language=language,
        source_url=source_url,
        local_path=pdf_path.relative_to(PROJECT_ROOT).as_posix(),
        license_name="Creative Commons Attribution 4.0 International (CC BY 4.0)",
        license_url=IPAQ_LICENSE_URL,
        redistribution_permitted=True,
        permission_basis=IPAQ_LICENSE_NOTICE,
        accessed_on=date(2026, 9, 27),
        sha256=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
    )


def build_ipaq_catalog() -> QuestionnaireParent:
    """Build standard adult English/German and elderly English IPAQ versions.

    Standard short-form source documentation states ages 15-69. IPAQ-E is a
    distinct elderly form; no precise minimum age is invented here because the
    exact cut-off should follow the evidence for the selected study population.
    No derived MET score is calculated by this test-data builder.
    """
    general_source_url = "https://drive.google.com/file/d/1LMCwPR0ddtdkb3uIuKPccip7ooD8wmrf/view"
    german_source_url = "https://drive.google.com/file/d/1jQe2uVCnYggvF93OPU_i0dDU6jyLFXA7/view"
    elderly_source_url = "https://drive.google.com/file/d/1JT2W8v0-PHaMs8mT9JT2WEyW0DAAkc_i/view"
    general_citation = (
        "Craig CL et al. International physical activity questionnaire: 12-country "
        "reliability and validity. Med Sci Sports Exerc. 2003;35(8):1381-1395. "
        "doi:10.1249/01.MSS.0000078924.61453.FB."
    )

    english_version = QuestionnaireVersion(
        version_id="ipaq_short_en_v1",
        language="en",
        locale="en-US",
        display_name="IPAQ Short Last 7 Days Self-Administered (English)",
        form_type="short",
        target_populations=[
            TargetPopulation(
                group_name="young and middle-aged adults",
                minimum_age_years=15,
                maximum_age_years=69,
                notes="Age range printed on the official English short-form PDF.",
            )
        ],
        publication_year=2003,
        source_citation=general_citation,
        source_doi="10.1249/01.MSS.0000078924.61453.FB",
        source_documents=[
            _source_document(
                title="IPAQ Short Last 7 Days Self-Administered English form",
                language="en",
                source_url=general_source_url,
                pdf_filename="physical_activity/ipaq/ipaq_short_en.pdf",
            )
        ],
        metadata=QuestionnaireMetadata(
            keywords=["physical activity", "exercise", "movement", "public health"],
            search_aliases=["IPAQ", "IPAQ short", "International Physical Activity Questionnaire"],
            characteristics=["self-report", "7-day-recall", "self-administered", "adult-form"],
            notes="Official form recommends no changes to question order or wording.",
        ),
        items=_short_form_items("ipaq_en", "en"),
    )
    german_version = QuestionnaireVersion(
        version_id="ipaq_short_de_de_v1",
        language="de",
        locale="de-DE",
        display_name="IPAQ Kurzform letzte 7 Tage, selbstadministriert (Deutsch)",
        form_type="short",
        variant_types=["translation"],
        based_on=[
            QuestionnaireVersionReference(
                instrument_id="ipaq", version_id=english_version.version_id
            )
        ],
        target_populations=[
            TargetPopulation(
                group_name="young and middle-aged adults",
                minimum_age_years=15,
                maximum_age_years=69,
                notes="Original form age range; translation accuracy is not endorsed by IPAQ. ",
            )
        ],
        source_documents=[
            _source_document(
                title="IPAQ short self-administered German form (revised June 2016)",
                language="de",
                source_url=german_source_url,
                pdf_filename="physical_activity/ipaq/ipaq_short_de_de.pdf",
            )
        ],
        metadata=QuestionnaireMetadata(
            keywords=["körperliche Aktivität", "Bewegung", "Gesundheitsförderung", "Public Health"],
            search_aliases=[
                "IPAQ Kurzform",
                "International Physical Activity Questionnaire Deutsch",
            ],
            characteristics=["self-report", "7-day-recall", "self-administered", "adult-form"],
            notes=(
                "The official IPAQ download page says researcher-submitted translations are "
                "provided as-is and their accuracy has not been checked."
            ),
        ),
        items=_short_form_items("ipaq_de_de", "de"),
    )
    elderly_version = QuestionnaireVersion(
        version_id="ipaq_elderly_en_v1",
        language="en",
        locale="en-US",
        display_name="IPAQ-E English",
        form_type="custom",
        variant_types=["population_adaptation"],
        based_on=[
            QuestionnaireVersionReference(
                instrument_id="ipaq", version_id=english_version.version_id
            )
        ],
        target_populations=[
            TargetPopulation(
                group_name="older adults",
                notes=(
                    "Official file is titled IPAQ-E (Elderly); no numerical cutoff is "
                    "assigned here without matching validation-study evidence."
                ),
            )
        ],
        source_documents=[
            _source_document(
                title="IPAQ-E English form",
                language="en",
                source_url=elderly_source_url,
                pdf_filename="physical_activity/ipaq/ipaq_elderly_short_en.pdf",
            )
        ],
        metadata=QuestionnaireMetadata(
            keywords=["physical activity", "older adults", "aging", "movement"],
            search_aliases=["IPAQ-E", "IPAQ Elderly"],
            characteristics=[
                "self-report",
                "7-day-recall",
                "self-administered",
                "older-adult-form",
            ],
            notes=(
                "IPAQ-E is maintained as a distinct form and must not be treated as the "
                "standard adult short form."
            ),
        ),
        items=_short_form_items("ipaq_e_en", "en", elderly=True),
    )
    return QuestionnaireParent(
        instrument_id="ipaq",
        name_full="International Physical Activity Questionnaire",
        construct_ontology=[],
        is_commercial=False,
        metadata=QuestionnaireMetadata(
            keywords=["physical activity", "movement", "health behavior"],
            search_aliases=["IPAQ", "International Physical Activity Questionnaire"],
        ),
        versions=[english_version, german_version, elderly_version],
    )


def write_ipaq_catalog(
    output_directory: Path = OUTPUT_DIRECTORY,
) -> Path:
    """Write the validated IPAQ family and return its JSON path."""
    output_directory.mkdir(parents=True, exist_ok=True)
    instrument = build_ipaq_catalog()
    output_path = output_directory / "ipaq.json"
    try:
        output_path.write_text(
            json.dumps(instrument.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        LOGGER.exception("Could not write IPAQ test catalog to %s", output_path)
        raise
    LOGGER.info("Wrote %s with %d variants", output_path, len(instrument.versions))
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        write_ipaq_catalog()
    except (OSError, ValueError):
        LOGGER.exception("Could not build the IPAQ catalog")
        raise SystemExit(1) from None
