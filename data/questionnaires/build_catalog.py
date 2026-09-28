"""Build the redistribution-cleared PHQ-9 and GAD-7 questionnaire fixtures.

The item wording in this module is transcribed from the official PHQ Screeners
forms bundled alongside this file. Their source site explicitly permits
reproduction, translation, display, and distribution. Do not add instruments to
this script until their item-text and document redistribution rights have been
verified for the intended repository and users.
"""

import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (  # noqa: E402, I001
    ItemSchema,
    MeSHTerm,
    QuestionnaireContributor,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    QuestionnaireVersionReference,
    ResponseOption,
    ScoringAlgorithm,
    TargetPopulation,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_PDF_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "forms"
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"
OFFICIAL_PHQ_PAGE = "https://www.phqscreeners.com/select-screener"
PHQ_LICENSE_NOTICE = (
    "The official PHQ Screeners page states that PHQ/GAD-7 screeners and "
    "translations may be reproduced, translated, displayed, and distributed "
    "without permission. The downloaded form also carries this notice."
)


@dataclass(frozen=True)
class _LocalizedFormSpec:
    """Typed source descriptor for one official language/locale form."""

    version_id: str
    language: str
    locale: str
    display_name: str
    prompts: tuple[str, ...]
    response_labels: tuple[str, ...]
    response_set_ref: str
    pdf_filename: str
    source_url: str
    base_version_id: str | None

PHQ9_EN_ITEMS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    (
        "Feeling bad about yourself — or that you are a failure or have let yourself or "
        "your family down"
    ),
    "Trouble concentrating on things, such as reading the newspaper or watching television",
    (
        "Moving or speaking so slowly that other people could have noticed? Or the opposite — "
        "being so fidgety or restless that you have been moving around a lot more than usual"
    ),
    "Thoughts that you would be better off dead or of hurting yourself in some way",
]

PHQ9_DE_ITEMS = [
    "Wenig Interesse oder Freude an Ihren Tätigkeiten",
    "Niedergeschlagenheit, Schwermut oder Hoffnungslosigkeit",
    "Schwierigkeiten, ein- oder durchzuschlafen, oder vermehrter Schlaf",
    "Müdigkeit oder Gefühl, keine Energie zu haben",
    "Verminderter Appetit oder übermäßiges Bedürfnis zu essen",
    (
        "Schlechte Meinung von sich selbst; Gefühl, ein Versager zu sein oder die Familie "
        "enttäuscht zu haben"
    ),
    "Schwierigkeiten, sich auf etwas zu konzentrieren, z. B. beim Zeitungslesen oder Fernsehen",
    (
        "Waren Ihre Bewegungen oder Ihre Sprache so verlangsamt, dass es auch anderen "
        "auffallen würde? Oder waren Sie im Gegenteil zappelig oder ruhelos und hatten "
        "dadurch einen stärkeren Bewegungsdrang als sonst?"
    ),
    "Gedanken, dass Sie lieber tot wären oder sich Leid zufügen möchten",
]

GAD7_EN_ITEMS = [
    "Feeling nervous, anxious or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid as if something awful might happen",
]

GAD7_DE_AT_ITEMS = [
    "Gefühle der Nervosität, Ängstlichkeit oder Anspannung",
    "Unfähigkeit, Sorgen zu stoppen oder zu kontrollieren",
    "Übermäßige Sorgen bezüglich verschiedener Angelegenheiten",
    "Schwierigkeiten, sich zu entspannen",
    "So rastlos sein, dass das Stillsitzen schwer fällt",
    "Schnelle Verärgerung oder Gereiztheit",
    "Angstgefühle, so als könnte etwas Schreckliches passieren",
]

GAD7_DE_CH_ITEMS = [
    "Gefühle der Nervosität, Ängstlichkeit oder Anspannung",
    "Nicht in der Lage sein, Sorgen zu stoppen oder zu kontrollieren",
    "Übermässige Sorgen bezüglich verschiedener Angelegenheiten",
    "Schwierigkeiten, sich zu entspannen",
    "So rastlos sein, dass das Stillsitzen schwer fällt",
    "Schnelle Verärgerung oder Gereiztheit",
    "Gefühl der Angst, so als würde etwas Schreckliches passieren",
]

PHQ9_EN_RESPONSE_LABELS = [
    "Not at all",
    "Several days",
    "More than half the days",
    "Nearly every day",
]
PHQ9_DE_RESPONSE_LABELS = [
    "Überhaupt nicht",
    "An einzelnen Tagen",
    "An mehr als der Hälfte der Tage",
    "Beinahe jeden Tag",
]
GAD7_DE_AT_RESPONSE_LABELS = [
    "Nie",
    "An manchen Tagen",
    "An mehr als der Hälfte der Tage",
    "Beinahe jeden Tag",
]
GAD7_DE_CH_RESPONSE_LABELS = [
    "Überhaupt nicht",
    "An einzelnen Tagen",
    "An mehr als der Hälfte der Tage",
    "Beinahe jeden Tag",
]
PHQ9_IMPACT_EN_LABELS = [
    "Not difficult at all",
    "Somewhat difficult",
    "Very difficult",
    "Extremely difficult",
]
PHQ9_IMPACT_DE_LABELS = [
    "Überhaupt nicht erschwert",
    "Etwas erschwert",
    "Stark erschwert",
    "Extrem erschwert",
]

PHQ_AUTHORS = [
    QuestionnaireContributor(name="Kurt Kroenke", role="author"),
    QuestionnaireContributor(name="Robert L. Spitzer", role="author"),
    QuestionnaireContributor(name="Janet B. W. Williams", role="author"),
]
GAD_AUTHORS = [
    QuestionnaireContributor(name="Robert L. Spitzer", role="author"),
    QuestionnaireContributor(name="Kurt Kroenke", role="author"),
    QuestionnaireContributor(name="Janet B. W. Williams", role="author"),
    QuestionnaireContributor(name="Bernd Löwe", role="author"),
]


def _response_options(labels: Sequence[str], *, scored: bool = True) -> list[ResponseOption]:
    """Create response codes in the order shown on the official instrument form."""
    return [
        ResponseOption(code=code, label=label, score=float(code) if scored else None)
        for code, label in enumerate(labels)
    ]


def _make_items(
    prefix: str,
    dimensions: Sequence[str],
    prompts: Sequence[str],
    response_set_ref: str,
    *,
    scored: bool = True,
) -> list[ItemSchema]:
    """Create individually identified items while preserving source item order."""
    return [
        ItemSchema(
            item_id=f"{prefix}_{index:02d}",
            variable_name=f"{prefix}_{index:02d}",
            dimension=dimension,
            prompt_text=prompt,
            response_set_ref=response_set_ref,
            is_scored=scored,
            redcap_field_type="radio",
            metadata=QuestionnaireMetadata(
                characteristics=["self-report", "screening-item"]
            ),
        )
        for index, (dimension, prompt) in enumerate(zip(dimensions, prompts, strict=True), start=1)
    ]


def _add_item_characteristic(
    items: list[ItemSchema], item_id: str, characteristic: str
) -> list[ItemSchema]:
    """Return items with one explicitly tagged item copied immutably.

    This helper is used for PHQ-9 item 9, whose content should be identifiable
    to downstream interfaces without turning the tag into a clinical rule.
    """
    for item_index, item in enumerate(items):
        if item.item_id == item_id:
            updated_metadata = item.metadata.model_copy(
                update={
                    "characteristics": [*item.metadata.characteristics, characteristic]
                }
            )
            return [
                *items[:item_index],
                item.model_copy(update={"metadata": updated_metadata}),
                *items[item_index + 1 :],
            ]
    raise ValueError(f"Cannot tag missing questionnaire item {item_id!r}")


def _source_document(
    *,
    title: str,
    language: str,
    pdf_filename: str | None,
    source_url: str,
    permission_basis: str,
    pdf_directory: Path,
    redistribution_permitted: bool,
    document_type: str = "questionnaire_form",
    license_name: str = "PHQ Screeners reproduction notice",
) -> QuestionnaireSourceDocument:
    """Create dated source provenance, including a hash for bundled PDFs."""
    local_path: str | None = None
    checksum: str | None = None
    if pdf_filename is not None:
        pdf_path = pdf_directory / pdf_filename
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Expected source PDF is missing: {pdf_path}")
        checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        local_path = pdf_path.relative_to(PROJECT_ROOT).as_posix()
    return QuestionnaireSourceDocument(
        title=title,
        document_type=document_type,
        language=language,
        source_url=source_url,
        local_path=local_path,
        license_name=license_name,
        license_url=OFFICIAL_PHQ_PAGE,
        redistribution_permitted=redistribution_permitted,
        permission_basis=permission_basis,
        accessed_on=date(2026, 9, 27),
        sha256=checksum,
    )


def _base_version_reference(instrument_id: str, version_id: str) -> QuestionnaireVersionReference:
    """Create an explicit ancestry reference to an original-language version."""
    return QuestionnaireVersionReference(instrument_id=instrument_id, version_id=version_id)


def build_phq9_versions(pdf_directory: Path) -> QuestionnaireParent:
    """Build English and Germany-German PHQ-9 versions with the separate impact item."""
    phq9_doi = "https://doi.org/10.1046/j.1525-1497.2001.016009606.x"
    response_sets = {
        "frequency_4_en": _response_options(PHQ9_EN_RESPONSE_LABELS),
        "frequency_4_de": _response_options(PHQ9_DE_RESPONSE_LABELS),
        "impact_4_en": _response_options(PHQ9_IMPACT_EN_LABELS, scored=False),
        "impact_4_de": _response_options(PHQ9_IMPACT_DE_LABELS, scored=False),
    }
    dimensions = [
        "interest",
        "mood",
        "sleep",
        "energy",
        "appetite",
        "self_evaluation",
        "concentration",
        "psychomotor",
        "self_harm_thoughts",
    ]
    english_items = _make_items("phq9_en", dimensions, PHQ9_EN_ITEMS, "frequency_4_en")
    german_items = _make_items("phq9_de", dimensions, PHQ9_DE_ITEMS, "frequency_4_de")
    english_items = _add_item_characteristic(
        english_items, "phq9_en_09", "suicide-related-thoughts"
    )
    german_items = _add_item_characteristic(
        german_items, "phq9_de_09", "suicide-related-thoughts"
    )
    english_items.append(
        ItemSchema(
            item_id="phq9_en_function_impact",
            variable_name="phq9_en_impact",
            dimension="functional_impact",
            prompt_text=(
                "If you checked off any problems, how difficult have these problems made it "
                "to do your work, take care of things at home, or get along with other people?"
            ),
            response_set_ref="impact_4_en",
            is_scored=False,
            metadata=QuestionnaireMetadata(characteristics=["self-report", "functional-impact"]),
        )
    )
    german_items.append(
        ItemSchema(
            item_id="phq9_de_function_impact",
            variable_name="phq9_de_impact",
            dimension="functional_impact",
            prompt_text=(
                "Wenn eines oder mehrere der bisher in diesem Fragebogen beschriebenen Probleme "
                "bei Ihnen vorliegen, wie sehr haben diese Probleme es Ihnen erschwert, Ihre "
                "Arbeit zu tun, Ihren Haushalt zu regeln oder mit anderen Menschen "
                "zurecht zu kommen?"
            ),
            response_set_ref="impact_4_de",
            is_scored=False,
            metadata=QuestionnaireMetadata(characteristics=["self-report", "functional-impact"]),
        )
    )
    score = ScoringAlgorithm(
        output_variable="phq9_total",
        method="sum",
        target_items=[f"phq9_en_{index:02d}" for index in range(1, 10)],
        missing_data_rules="Follow the official PHQ-9 scoring guidance; do not impute by default.",
    )
    base_citation = (
        "Kroenke K, Spitzer RL, Williams JBW. The PHQ-9: Validity of a Brief Depression "
        "Severity Measure. J Gen Intern Med. 2001;16:606-613."
    )
    english_pdf_url = (
        "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/PHQ-9_English.pdf"
    )
    german_pdf_url = (
        "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/"
        "PHQ9_German%20for%20Germany.pdf"
    )
    english_version = QuestionnaireVersion(
        version_id="phq9_en_v1",
        language="en",
        display_name="PHQ-9 English (United States source form)",
        locale="en-US",
        variant_types=[],
        target_populations=[
            TargetPopulation(
                group_name="Primary-care patients in the original validation study",
                notes="Describes the cited study sample, not an exclusive use restriction.",
            )
        ],
        publication_year=2001,
        source_citation=base_citation,
        source_doi="10.1046/j.1525-1497.2001.016009606.x",
        source_documents=[
            _source_document(
                title="PHQ-9 English form",
                language="en",
                pdf_filename="mental_health/phq9/phq9_en.pdf",
                source_url=english_pdf_url,
                permission_basis=PHQ_LICENSE_NOTICE,
                pdf_directory=pdf_directory,
                redistribution_permitted=True,
            ),
            _source_document(
                title=base_citation,
                language="en",
                pdf_filename=None,
                source_url=phq9_doi,
                permission_basis="Citation link only; the journal article PDF is not bundled.",
                pdf_directory=pdf_directory,
                redistribution_permitted=False,
                document_type="validation_study",
                license_name="Copyright remains with the publisher/authors; link only",
            ),
        ],
        metadata=QuestionnaireMetadata(
            keywords=["depression", "depressive symptoms", "mental health", "primary care"],
            search_aliases=["PHQ-9", "Patient Health Questionnaire-9"],
            mesh_terms=[
                MeSHTerm(descriptor="Depression"),
                MeSHTerm(descriptor="Depressive Disorder"),
            ],
            characteristics=["self-report", "symptom-screening", "14-day-reference-period"],
            notes="This screening measure is not by itself a clinical diagnosis.",
        ),
        response_sets={
            "frequency_4_en": response_sets["frequency_4_en"],
            "impact_4_en": response_sets["impact_4_en"],
        },
        items=english_items,
        scoring_algorithms=[score],
    )
    german_version = QuestionnaireVersion(
        version_id="phq9_de_de_v1",
        language="de",
        display_name="PHQ-9 Deutsch (Deutschland)",
        locale="de-DE",
        variant_types=["translation"],
        based_on=[_base_version_reference("phq9", english_version.version_id)],
        source_citation=base_citation,
        source_documents=[
            _source_document(
                title="PHQ-9 German for Germany form",
                language="de",
                pdf_filename="mental_health/phq9/phq9_de_de.pdf",
                source_url=german_pdf_url,
                permission_basis=PHQ_LICENSE_NOTICE,
                pdf_directory=pdf_directory,
                redistribution_permitted=True,
            )
        ],
        metadata=QuestionnaireMetadata(
            keywords=[
                "Depression",
                "depressive Symptome",
                "psychische Gesundheit",
                "Hausarztpraxis",
            ],
            search_aliases=["PHQ-9 Deutsch", "Patient Health Questionnaire-9 Deutsch"],
            mesh_terms=[
                MeSHTerm(descriptor="Depression"),
                MeSHTerm(descriptor="Depressive Disorder"),
            ],
            characteristics=["self-report", "symptom-screening", "14-day-reference-period"],
            notes=(
                "Deutschland-Fassung; nicht mit Schweizer/österreichischen Varianten "
                "gleichsetzen."
            ),
        ),
        response_sets={
            "frequency_4_de": response_sets["frequency_4_de"],
            "impact_4_de": response_sets["impact_4_de"],
        },
        items=german_items,
        scoring_algorithms=[
            score.model_copy(
                update={"target_items": [f"phq9_de_{index:02d}" for index in range(1, 10)]}
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id="phq9",
        name_full="Patient Health Questionnaire-9",
        construct_ontology=["depressive symptom severity"],
        is_commercial=False,
        contributors=PHQ_AUTHORS,
        metadata=QuestionnaireMetadata(
            description=(
                "Nine-item self-report measure of depressive symptom frequency and severity "
                "during the preceding two weeks."
            ),
            intended_use=(
                "Screening and monitoring depressive symptoms in primary care and research; "
                "the score is not a diagnosis by itself."
            ),
            name_origin=(
                "Patient Health Questionnaire, nine-item depression module; commonly shortened "
                "to PHQ-9."
            ),
            development_history=(
                "Published and validated as the nine-item depression module of the PHQ in 2001; "
                "language versions must be interpreted with their own evidence."
            ),
            measurement_rationale=(
                "The items represent core depressive symptom domains and use a common two-week "
                "frequency frame to support a severity summary."
            ),
            interpretation_notes=(
                "Cutoffs, diagnostic accuracy, and response to change depend on the setting, "
                "population, language version, and clinical assessment."
            ),
            keywords=["depression", "mental health", "primary care"],
            search_aliases=["PHQ-9", "PHQ9", "Patient Health Questionnaire"],
        ),
        versions=[english_version, german_version],
    )


def build_gad7_versions(pdf_directory: Path) -> QuestionnaireParent:
    """Build English, Austrian-German, and Swiss-German GAD-7 versions."""
    gad7_doi = "https://doi.org/10.1001/archinte.166.10.1092"
    dimensions = [
        "nervousness",
        "worry_control",
        "excessive_worry",
        "relaxation",
        "restlessness",
        "irritability",
        "fear",
    ]
    version_data = [
        _LocalizedFormSpec(
            version_id="gad7_en_v1",
            language="en",
            locale="en-US",
            display_name="GAD-7 English (United States source form)",
            prompts=tuple(GAD7_EN_ITEMS),
            response_labels=tuple(PHQ9_EN_RESPONSE_LABELS),
            response_set_ref="frequency_4_en",
            pdf_filename="mental_health/gad7/gad7_en.pdf",
            source_url=(
                "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/"
                "GAD-7_English.pdf"
            ),
            base_version_id=None,
        ),
        _LocalizedFormSpec(
            version_id="gad7_de_at_v1",
            language="de",
            locale="de-AT",
            display_name="GAD-7 Deutsch (Österreich)",
            prompts=tuple(GAD7_DE_AT_ITEMS),
            response_labels=tuple(GAD7_DE_AT_RESPONSE_LABELS),
            response_set_ref="frequency_4_de_at",
            pdf_filename="mental_health/gad7/gad7_de_at.pdf",
            source_url=(
                "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/"
                "GAD7_German%20for%20Austria.pdf"
            ),
            base_version_id="gad7_en_v1",
        ),
        _LocalizedFormSpec(
            version_id="gad7_de_ch_v1",
            language="de",
            locale="de-CH",
            display_name="GAD-7 Deutsch (Schweiz)",
            prompts=tuple(GAD7_DE_CH_ITEMS),
            response_labels=tuple(GAD7_DE_CH_RESPONSE_LABELS),
            response_set_ref="frequency_4_de_ch",
            pdf_filename="mental_health/gad7/gad7_de_ch.pdf",
            source_url=(
                "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/"
                "GAD7_German%20for%20Switzerland.pdf"
            ),
            base_version_id="gad7_en_v1",
        ),
    ]
    versions: list[QuestionnaireVersion] = []
    for data in version_data:
        version_id = data.version_id
        language = data.language
        locale = data.locale
        items = _make_items(
            version_id.replace("_v1", ""),
            dimensions,
            data.prompts,
            data.response_set_ref,
        )
        source_documents = [
            _source_document(
                title=f"GAD-7 form: {data.display_name}",
                language=language,
                pdf_filename=data.pdf_filename,
                source_url=data.source_url,
                permission_basis=PHQ_LICENSE_NOTICE,
                pdf_directory=pdf_directory,
                redistribution_permitted=True,
            )
        ]
        if data.base_version_id is None:
            source_documents.append(
                _source_document(
                    title=(
                        "Spitzer RL, Kroenke K, Williams JBW, Löwe B. A brief measure for "
                        "assessing generalized anxiety disorder: the GAD-7. 2006."
                    ),
                    language="en",
                    pdf_filename=None,
                    source_url=gad7_doi,
                    permission_basis="Citation link only; the journal article PDF is not bundled.",
                    pdf_directory=pdf_directory,
                    redistribution_permitted=False,
                    document_type="validation_study",
                    license_name="Copyright remains with the publisher/authors; link only",
                )
            )
        versions.append(
            QuestionnaireVersion(
                version_id=version_id,
                language=language,
                locale=locale,
                    display_name=data.display_name,
                variant_types=["translation"] if data.base_version_id else [],
                based_on=(
                    [_base_version_reference("gad7", data.base_version_id)]
                    if data.base_version_id
                    else []
                ),
                publication_year=2006 if data.base_version_id is None else None,
                source_citation=(
                    "Spitzer RL, Kroenke K, Williams JBW, Löwe B. A brief measure for assessing "
                    "generalized anxiety disorder: the GAD-7. Arch Intern Med. 2006;166:1092-1097."
                    if data.base_version_id is None
                    else None
                ),
                source_doi=(
                    "10.1001/archinte.166.10.1092"
                    if data.base_version_id is None
                    else None
                ),
                source_documents=source_documents,
                metadata=QuestionnaireMetadata(
                    keywords=(
                        ["anxiety", "generalized anxiety", "primary care", "Angst", "Sorgen"]
                        if language == "en"
                        else ["Angst", "Ängstlichkeit", "Sorgen", "psychische Gesundheit"]
                    ),
                    search_aliases=["GAD-7", "GAD7", "Generalized Anxiety Disorder-7"],
                    mesh_terms=[
                        MeSHTerm(descriptor="Anxiety"),
                        MeSHTerm(descriptor="Anxiety Disorders"),
                    ],
                    characteristics=["self-report", "symptom-screening", "14-day-reference-period"],
                    notes=(
                        f"Official source form for locale {locale}; wording is kept "
                        "variant-specific."
                    ),
                ),
                response_sets={
                    data.response_set_ref: _response_options(data.response_labels)
                },
                items=items,
                scoring_algorithms=[
                    ScoringAlgorithm(
                        output_variable="gad7_total",
                        method="sum",
                        target_items=[item.item_id for item in items],
                        missing_data_rules=(
                            "Follow the official GAD-7 scoring guidance; do not impute "
                            "by default."
                        ),
                    )
                ],
            )
        )
    return QuestionnaireParent(
        instrument_id="gad7",
        name_full="Generalized Anxiety Disorder-7",
        construct_ontology=["generalized anxiety symptom severity"],
        is_commercial=False,
        contributors=GAD_AUTHORS,
        metadata=QuestionnaireMetadata(
            description=(
                "Seven-item self-report measure of generalized anxiety symptom frequency "
                "during the preceding two weeks."
            ),
            intended_use=(
                "Screening and monitoring anxiety symptoms in primary care and research; "
                "it does not establish a diagnosis without further assessment."
            ),
            name_origin=(
                "Generalized Anxiety Disorder questionnaire, seven-item form; abbreviated "
                "GAD-7."
            ),
            development_history=(
                "Introduced and evaluated by Spitzer, Kroenke, Williams, and Lowe in 2006; "
                "regional translations are separate versions in this catalog."
            ),
            measurement_rationale=(
                "The items sample common cognitive, emotional, and physiological anxiety "
                "symptoms with a shared two-week frequency frame."
            ),
            interpretation_notes=(
                "Thresholds and diagnostic performance are context- and language-specific; "
                "use the official scoring and clinical guidance for the chosen version."
            ),
            keywords=["anxiety", "generalized anxiety", "mental health"],
            search_aliases=["GAD-7", "GAD7", "Generalized Anxiety Disorder-7"],
        ),
        versions=versions,
    )


def build_real_questionnaire_catalog(
    pdf_directory: Path = DEFAULT_PDF_DIRECTORY,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> list[Path]:
    """Validate and write the locally licensed PHQ-9 and GAD-7 JSON files.

    The builder never downloads files. Every bundled PDF must already exist in
    ``pdf_directory`` and receives a SHA-256 checksum in its source record.
    Existing JSON output is replaced deterministically; unrelated files remain
    untouched. Errors are logged without swallowing the underlying failure.
    """
    instruments = [build_phq9_versions(pdf_directory), build_gad7_versions(pdf_directory)]
    output_directory.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []
    for instrument in instruments:
        output_path = output_directory / f"{instrument.instrument_id}.json"
        try:
            output_path.write_text(
                json.dumps(instrument.model_dump(mode="json"), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            LOGGER.exception("Could not write questionnaire catalog file %s", output_path.name)
            raise
        generated_paths.append(output_path)
        LOGGER.info(
            "Wrote %s with %d language/locale variants",
            output_path,
            len(instrument.versions),
        )
    return generated_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        build_real_questionnaire_catalog()
    except (OSError, ValueError):
        LOGGER.exception("Could not build the real questionnaire test catalog")
        raise SystemExit(1) from None
