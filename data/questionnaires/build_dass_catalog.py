"""Build permission-cleared adult DASS-21 and youth DASS-Y JSON records.

The Psychology Foundation of Australia states that its DASS forms are public
domain and may be copied without restriction, provided they are not modified
or sold for profit. Its translation records say translator-provided translations
must also remain public domain, and warn that translation adequacy/validity is
not assured by the Foundation. This builder preserves the wording of the exact
bundled forms; it does not translate or normalize the instruments.
"""

import hashlib
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (  # noqa: E402, I001
    ItemSchema,
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
PDF_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "forms"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"
DASS_FAQ_URL = "https://www2.psy.unsw.edu.au/dass/DASSFAQ.htm"
DASS_DOWNLOAD_URL = "https://www2.psy.unsw.edu.au/dass/down.htm"
DASS_TRANSLATIONS_URL = "https://www2.psy.unsw.edu.au/dass/DASS%20Translations.htm"
DASS_Y_PAGE_URL = "https://www2.psy.unsw.edu.au/dass/DASSY.htm"
DASS_Y_TRANSLATIONS_URL = "https://www2.psy.unsw.edu.au/dass/DASS-Y%20Translations.htm"
DASS_BASE_URL = "https://www2.psy.unsw.edu.au/dass/"
DASS21_DE_PAGE_URL = (
    "https://www2.psy.unsw.edu.au/dass/German/DASS21%20Nilges%20%26%20Essau/"
    "German%20DASS21%20Nilges%20Essau.htm"
)
DASS21_DE_PDF_PATH = (
    "German/DASS21%20Nilges%20%26%20Essau/German%20DASS21.pdf"
)
DASS_Y_DE_PAGE_URL = (
    "https://www2.psy.unsw.edu.au/dass/DASS-Y%20German/"
    "Neuhoff%20%26%20Noorani-Yazdanabad%20German%20translation%20of%20DASS-Y.htm"
)
DASS_LICENSE_NAME = "Public domain; may be copied, not modified or sold for profit"
DASS_PERMISSION_BASIS = (
    "The official DASS Download page says forms may be downloaded and copied without "
    "restriction; scales may not be modified or sold for profit. Official FAQ states "
    "permission is not needed because the questionnaire is public domain."
)
TRANSLATION_QUALITY_NOTE = (
    "Translation is listed by the official DASS site. The site explicitly does not "
    "assure translation adequacy or validity; verify population-specific evidence "
    "before interpreting or comparing scores."
)

DASS21_EN_ITEMS = [
    "I found it hard to wind down",
    "I was aware of dryness of my mouth",
    "I couldn't seem to experience any positive feeling at all",
    (
        "I experienced breathing difficulty (eg, excessively rapid breathing, breathlessness "
        "in the absence of physical exertion)"
    ),
    "I found it difficult to work up the initiative to do things",
    "I tended to over-react to situations",
    "I experienced trembling (eg, in the hands)",
    "I felt that I was using a lot of nervous energy",
    "I was worried about situations in which I might panic and make a fool of myself",
    "I felt that I had nothing to look forward to",
    "I found myself getting agitated",
    "I found it difficult to relax",
    "I felt down-hearted and blue",
    "I was intolerant of anything that kept me from getting on with what I was doing",
    "I felt I was close to panic",
    "I was unable to become enthusiastic about anything",
    "I felt I wasn't worth much as a person",
    "I felt that I was rather touchy",
    (
        "I was aware of the action of my heart in the absence of physical exertion (eg, "
        "sense of heart rate increase, heart missing a beat)"
    ),
    "I felt scared without any good reason",
    "I felt that life was meaningless",
]
DASS21_DE_ITEMS = [
    "Ich fand es schwer, mich zu beruhigen.",
    "Ich spürte, dass mein Mund trocken war.",
    "Ich konnte überhaupt keine positiven Gefühle mehr erleben",
    (
        "Ich hatte Atemprobleme (z.B. übermäßig schnelles Atmen, Atemlosigkeit ohne "
        "körperliche Anstrengung)."
    ),
    "Es fiel mir schwer, mich dazu aufzuraffen, Dinge zu erledigen.",
    "Ich tendierte dazu, auf Situationen überzureagieren.",
    "Ich zitterte (z.B. an den Händen).",
    "Ich fand alles anstrengend.",
    (
        "Ich machte mir Sorgen über Situationen, in denen ich in Panik geraten und mich "
        "lächerlich machen könnte."
    ),
    "Ich hatte das Gefühl, dass ich mich auf nichts mehr freuen konnte.",
    "Ich bemerkte, dass ich mich schnell aufregte.",
    "Ich fand es schwierig, mich zu entspannen.",
    "Ich fühlte mich niedergeschlagen und traurig.",
    (
        "Ich reagierte ungehalten auf alles, was mich davon abhielt, meine momentane "
        "Tätigkeit fortzuführen."
    ),
    "Ich fühlte mich einer Panik nahe.",
    "Ich war nicht in der Lage, mich für irgendetwas zu begeistern.",
    "Ich fühlte mich als Person nicht viel wert.",
    "Ich fand mich ziemlich empfindlich.",
    (
        "Ich habe meinen Herzschlag gespürt, ohne dass ich mich körperlich angestrengt "
        "hatte (z.B. Gefühl von Herzrasen oder Herzstolpern)."
    ),
    "Ich fühlte mich grundlos ängstlich.",
    "Ich empfand das Leben als sinnlos.",
]
DASS_Y_EN_ITEMS = [
    "I got upset about little things",
    "I felt dizzy, like I was about to faint",
    "I did not enjoy anything",
    (
        "I had trouble breathing (e.g. fast breathing), even though I wasn't exercising "
        "and I was not sick."
    ),
    "I hated my life",
    "I found myself over-reacting to situations",
    "My hands felt shaky",
    "I was stressing about lots of things",
    "I felt terrified",
    "There was nothing nice I could look forward to",
    "I was easily irritated",
    "I found it difficult to relax",
    "I could not stop feeling sad",
    "I got annoyed when people interrupted me",
    "I felt like I was about to panic",
    "I hated myself",
    "I felt like I was no good",
    "I was easily annoyed",
    "I could feel my heart beating really fast, even though I hadn't done any hard exercise",
    "I felt scared for no good reason",
    "I felt that life was terrible",
]
DASS_Y_DE_ITEMS = [
    "Ich regte mich über Kleinigkeiten auf",
    "Mir war schwindelig, wie wenn ich in Ohnmacht fallen würde",
    "Ich habe nichts genossen",
    (
        "Ich hatte Schwierigkeiten zu atmen (z.B. schnelles Atmen), obwohl ich keinen "
        "Sport machte und ich nicht krank war"
    ),
    "Ich hasste mein Leben",
    "Ich reagierte in Situationen über",
    "Meine Hände fühlten sich zittrig an",
    "Ich war wegen vieler Dinge gestresst",
    "Ich fühlte mich verschreckt",
    "Es gab nichts Schönes, auf das ich mich freuen konnte",
    "Ich war schnell gereizt",
    "Ich fand es schwierig mich zu entspannen",
    "Ich konnte nicht aufhören mich traurig zu fühlen",
    "Ich war genervt, wenn Leute mich unterbrachen",
    "Ich fühlte mich einer Panik nahe",
    "Ich hasste mich selbst",
    "Ich fühlte mich zu nichts zu gebrauchen",
    "Ich war schnell genervt",
    (
        "Ich konnte mein Herz schnell schlagen fühlen, obwohl ich mich nicht stark "
        "körperlich betätigt hatte"
    ),
    "Ich fühlte mich grundlos ängstlich",
    "Ich fand das Leben war furchtbar",
]

DASS21_EN_LABELS = [
    "Did not apply to me at all",
    "Applied to me to some degree, or some of the time",
    "Applied to me to a considerable degree, or a good part of the time",
    "Applied to me very much, or most of the time",
]
DASS21_DE_LABELS = [
    "Traf gar nicht auf mich zu",
    "Traf bis zu einem gewissen Grad auf mich zu oder manchmal",
    "Traf in beträchtlichem Maße auf mich zu oder ziemlich oft",
    "Traf sehr stark auf mich zu oder die meiste Zeit",
]
DASS_Y_EN_LABELS = ["Not true", "A little true", "Fairly true", "Very true"]
DASS_Y_DE_LABELS = ["Nicht zutraf", "Ein wenig zutraf", "Ziemlich zutraf", "Sehr stark zutraf"]

SCALE_ITEMS = {
    "depression": [3, 5, 10, 13, 16, 17, 21],
    "anxiety": [2, 4, 7, 9, 15, 19, 20],
    "stress": [1, 6, 8, 11, 12, 14, 18],
}


def _response_options(labels: Sequence[str]) -> list[ResponseOption]:
    """Assign the official ordered response choices values zero through three."""
    return [
        ResponseOption(code=index, label=label, score=float(index))
        for index, label in enumerate(labels)
    ]


def _items(prefix: str, prompts: Sequence[str]) -> list[ItemSchema]:
    """Create item records while retaining the source form's item order."""
    return [
        ItemSchema(
            item_id=f"{prefix}_{index:02d}",
            variable_name=f"{prefix}_{index:02d}",
            dimension=next(
                scale_name
                for scale_name, item_numbers in SCALE_ITEMS.items()
                if index in item_numbers
            ),
            prompt_text=prompt,
            response_set_ref="frequency_4",
            metadata=QuestionnaireMetadata(
                characteristics=["self-report", "negative-emotional-state"]
            ),
        )
        for index, prompt in enumerate(prompts, start=1)
    ]


def _score_definitions(prefix: str, *, youth: bool) -> list[ScoringAlgorithm]:
    """Build per-domain score definitions with version-specific multipliers."""
    algorithms: list[ScoringAlgorithm] = []
    for scale_name, item_numbers in SCALE_ITEMS.items():
        targets = [f"{prefix}_{item_number:02d}" for item_number in item_numbers]
        algorithms.append(
            ScoringAlgorithm(
                output_variable=f"{prefix}_{scale_name}_raw",
                method="sum",
                target_items=targets,
                multiplier=1.0,
                missing_data_rules=(
                    "Follow the official scoring guidance; do not infer a missing response."
                ),
            )
        )
        if not youth:
            algorithms.append(
                ScoringAlgorithm(
                    output_variable=f"{prefix}_{scale_name}_comparable",
                    method="sum",
                    target_items=targets,
                    multiplier=2.0,
                    missing_data_rules=(
                        "DASS-21 convention: multiply each seven-item subscale sum by two "
                        "to compare with full DASS scale ranges."
                    ),
                )
            )
    return algorithms


def _source_document(
    *,
    title: str,
    language: str,
    source_url: str,
    local_filename: str | None,
    source_directory: Path,
    document_type: str,
    license_name: str,
    permission_basis: str,
    redistribution_permitted: bool,
) -> QuestionnaireSourceDocument:
    """Record the official source, exact permission basis, and local PDF hash."""
    local_path: str | None = None
    checksum: str | None = None
    if local_filename is not None:
        pdf_path = source_directory / local_filename
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Required official DASS source file is missing: {pdf_path}")
        checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        local_path = pdf_path.relative_to(PROJECT_ROOT).as_posix()
    return QuestionnaireSourceDocument(
        title=title,
        document_type=document_type,
        language=language,
        source_url=source_url,
        local_path=local_path,
        license_name=license_name,
        license_url=DASS_FAQ_URL if "public domain" in license_name.casefold() else None,
        redistribution_permitted=redistribution_permitted,
        permission_basis=permission_basis,
        accessed_on=date(2026, 9, 27),
        sha256=checksum,
    )


def _make_version(
    *,
    instrument_id: str,
    version_id: str,
    prefix: str,
    language: str,
    locale: str,
    display_name: str,
    prompts: Sequence[str],
    response_labels: Sequence[str],
    pdf_filename: str,
    page_url: str,
    pdf_url: str,
    source_directory: Path,
    youth: bool,
    translation_contributors: list[QuestionnaireContributor] | None = None,
    translation_note: str | None = None,
    base_version_id: str | None = None,
) -> QuestionnaireVersion:
    """Construct one DASS edition while keeping age and score interpretation explicit."""
    source_documents = [
        _source_document(
            title=f"{display_name} official questionnaire form",
            language=language,
            source_url=pdf_url,
            local_filename=pdf_filename,
            source_directory=source_directory,
            document_type="questionnaire_form",
            license_name=DASS_LICENSE_NAME,
            permission_basis=DASS_PERMISSION_BASIS,
            redistribution_permitted=True,
        ),
        _source_document(
            title=f"{display_name} official translation/version record",
            language=language,
            source_url=page_url,
            local_filename=None,
            source_directory=source_directory,
            document_type="other",
            license_name="Official source record; linked only",
            permission_basis=(
                translation_note
                or "Official DASS source page identifies the form; linked, not copied."
            ),
            redistribution_permitted=False,
        ),
    ]
    return QuestionnaireVersion(
        version_id=version_id,
        language=language,
        locale=locale,
        display_name=display_name,
        form_type="short",
        variant_types=["translation"] if translation_contributors else [],
        contributors=translation_contributors or [],
        based_on=(
            [QuestionnaireVersionReference(instrument_id=instrument_id, version_id=base_version_id)]
            if base_version_id
            else []
        ),
        publication_year=2015 if translation_contributors and not youth else None,
        source_citation=(
            "Nilges P, Essau C. German translation and evaluation of the DASS-21. Schmerz. 2015."
            if translation_contributors and not youth
            else None
        ),
        source_documents=source_documents,
        target_populations=[
            TargetPopulation(
                group_name="children and adolescents" if youth else "people aged 14 and older",
                minimum_age_years=8 if youth else 14,
                maximum_age_years=17 if youth else None,
                notes=(
                    "Official DASS-Y age range; its scores are not directly comparable "
                    "with adult DASS/DASS21."
                    if youth
                    else "Official FAQ lower age guidance assumes typical language skills."
                ),
            )
        ],
        metadata=QuestionnaireMetadata(
            keywords=(
                ["depression", "anxiety", "stress", "psychological distress"]
                if language == "en"
                else ["Depression", "Angst", "Stress", "psychische Belastung"]
            ),
            search_aliases=["DASS", "DASS21", "DASS-21" if not youth else "DASS-Y"],
            characteristics=[
                "self-report",
                "negative-emotional-states",
                "seven-day-reference-period",
                "youth-form" if youth else "adult-form",
            ],
            notes=(
                translation_note
                or "Official source warns that the DASS is dimensional and is not a diagnosis."
            ),
        ),
        response_sets={"frequency_4": _response_options(response_labels)},
        items=_items(prefix, prompts),
        scoring_algorithms=_score_definitions(prefix, youth=youth),
    )


def build_dass_catalog(pdf_directory: Path = PDF_DIRECTORY) -> list[QuestionnaireParent]:
    """Build separate adult DASS-21 and youth DASS-Y instrument families.

    Official permission allows form copying but forbids modifications and sale.
    The builder keeps each English/German PDF's exact version separate and
    records the source's caveat that translations are not independently
    validated or certified by the Foundation.
    """
    adult_translation_note = (
        "Official DASS translation page lists the German form and identifies Paul Nilges "
        "and Cecilia Essau; the source does not certify translation validity."
    )
    youth_translation_note = (
        "Official DASS-Y translation page identifies Lina Neuhoff and Maria "
        "Noorani-Yazdanabad; the source does not certify translation validity."
    )
    dass21_english = _make_version(
        instrument_id="dass21",
        version_id="dass21_en_v1",
        prefix="dass21_en",
        language="en",
        locale="en-AU",
        display_name="DASS-21 English source form",
        prompts=DASS21_EN_ITEMS,
        response_labels=DASS21_EN_LABELS,
        pdf_filename="mental_health/dass21/dass21_en.pdf",
        page_url=DASS_DOWNLOAD_URL,
        pdf_url=f"{DASS_BASE_URL}Download%20files/Dass21.pdf",
        source_directory=pdf_directory,
        youth=False,
    )
    dass21_german = _make_version(
        instrument_id="dass21",
        version_id="dass21_de_de_v1",
        prefix="dass21_de_de",
        language="de",
        locale="de-DE",
        display_name="DASS-21 Deutsch (Nilges & Essau)",
        prompts=DASS21_DE_ITEMS,
        response_labels=DASS21_DE_LABELS,
        pdf_filename="mental_health/dass21/dass21_de_de.pdf",
        page_url=DASS21_DE_PAGE_URL,
        pdf_url=f"{DASS_BASE_URL}{DASS21_DE_PDF_PATH}",
        source_directory=pdf_directory,
        youth=False,
        translation_contributors=[
            QuestionnaireContributor(name="Paul Nilges", role="translator"),
            QuestionnaireContributor(name="Cecilia Essau", role="translator"),
        ],
        translation_note=adult_translation_note,
        base_version_id=dass21_english.version_id,
    )
    dass_y_english = _make_version(
        instrument_id="dass_y",
        version_id="dass_y_en_v1",
        prefix="dass_y_en",
        language="en",
        locale="en-AU",
        display_name="DASS-Y English source form",
        prompts=DASS_Y_EN_ITEMS,
        response_labels=DASS_Y_EN_LABELS,
        pdf_filename="mental_health/dass_y/dass_y_en.pdf",
        page_url=DASS_Y_PAGE_URL,
        pdf_url=f"{DASS_BASE_URL}Download%20files/DASS-Y.pdf",
        source_directory=pdf_directory,
        youth=True,
    )
    dass_y_german = _make_version(
        instrument_id="dass_y",
        version_id="dass_y_de_de_v1",
        prefix="dass_y_de_de",
        language="de",
        locale="de-DE",
        display_name="DASS-Y Deutsch (Neuhoff & Noorani-Yazdanabad)",
        prompts=DASS_Y_DE_ITEMS,
        response_labels=DASS_Y_DE_LABELS,
        pdf_filename="mental_health/dass_y/dass_y_de_de.pdf",
        page_url=DASS_Y_DE_PAGE_URL,
        pdf_url=f"{DASS_BASE_URL}DASS-Y%20German/DE_DASS-Y.pdf",
        source_directory=pdf_directory,
        youth=True,
        translation_contributors=[
            QuestionnaireContributor(
                name="Lina Neuhoff",
                role="translator",
                affiliation="Ruhr University Bochum",
            ),
            QuestionnaireContributor(
                name="Maria Noorani-Yazdanabad",
                role="translator",
                affiliation="Ruhr University Bochum",
            ),
        ],
        translation_note=youth_translation_note,
        base_version_id=dass_y_english.version_id,
    )
    return [
        QuestionnaireParent(
            instrument_id="dass21",
            name_full="Depression Anxiety Stress Scales-21",
            construct_ontology=[],
            is_commercial=False,
            contributors=[
                QuestionnaireContributor(name="S. H. Lovibond", role="author"),
                QuestionnaireContributor(name="P. F. Lovibond", role="author"),
            ],
            metadata=QuestionnaireMetadata(
                keywords=["depression", "anxiety", "stress", "distress"],
                search_aliases=["DASS-21", "DASS21", "Depression Anxiety Stress Scales"],
            ),
            versions=[dass21_english, dass21_german],
        ),
        QuestionnaireParent(
            instrument_id="dass_y",
            name_full="Depression Anxiety Stress Scales - Youth Version",
            construct_ontology=[],
            is_commercial=False,
            contributors=[
                QuestionnaireContributor(name="S. H. Lovibond", role="author"),
                QuestionnaireContributor(name="P. F. Lovibond", role="author"),
            ],
            metadata=QuestionnaireMetadata(
                keywords=["youth mental health", "depression", "anxiety", "stress"],
                search_aliases=["DASS-Y", "DASSY", "DASS Youth"],
            ),
            versions=[dass_y_english, dass_y_german],
        ),
    ]


def write_dass_catalog(
    instruments: Sequence[QuestionnaireParent],
    output_directory: Path = OUTPUT_DIRECTORY,
) -> list[Path]:
    """Write the supplied validated DASS families as deterministic JSON files."""
    output_directory.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []
    for instrument in instruments:
        output_path = output_directory / f"{instrument.instrument_id}.json"
        output_path.write_text(
            json.dumps(instrument.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        generated_paths.append(output_path)
        LOGGER.info("Wrote %s with %d variants", output_path, len(instrument.versions))
    return generated_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        write_dass_catalog(build_dass_catalog())
    except (OSError, ValueError):
        LOGGER.exception("Could not build the DASS catalogue")
        raise SystemExit(1) from None
