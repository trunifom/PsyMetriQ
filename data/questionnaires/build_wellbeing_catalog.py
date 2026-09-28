"""Build public-domain and link-only wellbeing/stress discovery records.

The Rosenberg items are bundled because the University of Maryland reports
that the scale is in the public domain. WHO-5, WEMWBS, GSE, and PSS are
metadata-only: records point to sources and note rights; they do not reproduce
item wording where open redistribution has not been established.
"""

import json
import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (  # noqa: E402
    ItemSchema,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    ResponseOption,
    ScoringAlgorithm,
    TargetPopulation,
)

LOGGER = logging.getLogger(__name__)
OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "json"
SOURCE_ACCESSED_ON = date(2026, 9, 28)
UMD_ROSENBERG_URL = "https://socy.umd.edu/quick-links/using-rosenberg-self-esteem-scale"
WHO5_URL = "https://www.who-5.org/"
WHO_COPYRIGHT_URL = "https://www.who.int/about/policies/publishing/copyright"
WEMWBS_LICENSE_URL = "https://warwick.ac.uk/services/innovations/wemwbs/licenses/"
WEMWBS_NONCOMMERCIAL_URL = (
    "https://warwick.ac.uk/services/innovations/wemwbs/licenses/non-commercial/"
)
GSE_ENGLISH_URL = "https://userpage.fu-berlin.de/health/engscal.htm"
GSE_LANGUAGE_URL = "https://userpage.fu-berlin.de/health/selfscal.htm"
PSS_SOURCE_URL = (
    "https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html"
)


def _source_document(
    *,
    title: str,
    document_type: str,
    source_url: str,
    license_name: str,
    license_url: str | None,
    redistribution_permitted: bool,
    permission_basis: str,
) -> QuestionnaireSourceDocument:
    return QuestionnaireSourceDocument(
        title=title,
        document_type=document_type,
        language="en",
        source_url=source_url,
        license_name=license_name,
        license_url=license_url,
        redistribution_permitted=redistribution_permitted,
        permission_basis=permission_basis,
        accessed_on=SOURCE_ACCESSED_ON,
    )


def build_rosenberg_self_esteem() -> QuestionnaireParent:
    """Create the English RSES record with the official public-domain reuse notice."""
    prompts = [
        "I feel that I am a person of worth, at least on an equal plane with others.",
        "I feel that I have a number of good qualities.",
        "All in all, I am inclined to feel that I am a failure.",
        "I am able to do things as well as most other people.",
        "I feel I do not have much to be proud of.",
        "I take a positive attitude toward myself.",
        "On the whole, I am satisfied with myself.",
        "I wish I could have more respect for myself.",
        "I certainly feel useless at times.",
        "At times I think I am no good at all.",
    ]
    item_ids = [f"rosenberg_{index:02d}" for index in range(1, 11)]
    response_ref = "rosenberg_four_point_agreement"
    options = [
        ResponseOption(code="SA", label="Strongly agree", score=3),
        ResponseOption(code="A", label="Agree", score=2),
        ResponseOption(code="D", label="Disagree", score=1),
        ResponseOption(code="SD", label="Strongly disagree", score=0),
    ]
    reverse_scored = {3, 5, 8, 9, 10}
    items = [
        ItemSchema(
            item_id=item_ids[index - 1],
            variable_name=f"rosenberg_{index:02d}",
            dimension="self_esteem",
            prompt_text=prompt,
            response_mode="categorical",
            response_set_ref=response_ref,
            is_reverse_scored=index in reverse_scored,
            redcap_field_type="radio",
        )
        for index, prompt in enumerate(prompts, start=1)
    ]
    return QuestionnaireParent(
        instrument_id="rosenberg_self_esteem",
        name_full="Rosenberg Self-Esteem Scale",
        construct_ontology=["self-esteem"],
        is_commercial=False,
        metadata=QuestionnaireMetadata(
            keywords=["self-esteem", "self-worth", "wellbeing"],
            notes="English source form; verify language- and population-specific evidence.",
        ),
        versions=[
            QuestionnaireVersion(
                version_id="rosenberg_en_v1",
                language="en",
                locale="en-US",
                display_name="Rosenberg Self-Esteem Scale (English)",
                publication_year=1965,
                source_citation="Rosenberg, M. (1965). Society and the Adolescent Self-Image.",
                source_documents=[
                    _source_document(
                        title="University of Maryland reuse and scoring notes",
                        document_type="questionnaire_form",
                        source_url=UMD_ROSENBERG_URL,
                        license_name="Public domain (University of Maryland reuse notice)",
                        license_url=None,
                        redistribution_permitted=True,
                        permission_basis=(
                            "The University of Maryland Department of Sociology states that the "
                            "scale is in the public domain, may be used without charge or notice, "
                            "and may be translated or adapted with scholarly attribution."
                        ),
                    )
                ],
                metadata=QuestionnaireMetadata(
                    keywords=["RSES", "Rosenberg Self-Esteem Scale"],
                    notes=(
                        "Reverse-score items 3, 5, 8, 9, and 10 (3 minus the response score) "
                        "before summing; the source describes a 0-30 total. Scoring is metadata, "
                        "not a validated calculation engine."
                    ),
                ),
                response_sets={response_ref: options},
                items=items,
                scoring_algorithms=[
                    ScoringAlgorithm(
                        output_variable="rosenberg_total",
                        method="sum",
                        target_items=item_ids,
                        missing_data_rules=(
                            "Reverse-score items 3, 5, 8, 9, and 10 before summing; "
                            "source range 0-30."
                        ),
                    )
                ],
            )
        ],
    )


def build_who5_link_only() -> QuestionnaireParent:
    """Add a searchable WHO-5 record without reproducing unverified item text."""
    return QuestionnaireParent(
        instrument_id="who5",
        name_full="WHO-5 Well-Being Index",
        construct_ontology=["subjective psychological well-being"],
        is_commercial=None,
        metadata=QuestionnaireMetadata(
            keywords=["WHO-5", "wellbeing", "well-being", "positive mental health"],
            notes=(
                "Metadata-only discovery record. Verify the copyright notice for the exact "
                "WHO-5 publication and any third-party credits before copying the items."
            ),
        ),
        versions=[
            QuestionnaireVersion(
                version_id="who5_en_v1",
                language="en",
                display_name="WHO-5 English (official source; link-only)",
                form_type="short",
                item_text_included=False,
                source_reported_item_count=5,
                source_reported_dimensions=["positive wellbeing"],
                source_documents=[
                    _source_document(
                        title="WHO-5 official site",
                        document_type="questionnaire_form",
                        source_url=WHO5_URL,
                        license_name="Exact publication terms not verified; link only",
                        license_url=WHO_COPYRIGHT_URL,
                        redistribution_permitted=False,
                        permission_basis=(
                            "The official WHO copyright policy requires checking the copyright "
                            "notice on the exact publication and any third-party credits. The "
                            "linked WHO-5 host redirects to the official regional site; item text "
                            "and PDFs are not included pending edition-specific rights review."
                        ),
                    )
                ],
                metadata=QuestionnaireMetadata(
                    keywords=["WHO-5", "WHO five-item wellbeing index"],
                    notes=(
                        "Open the official source and verify terms for the exact form/version. "
                        "Topp et al. (2015) review: DOI 10.1159/000376585; this is not the "
                        "underlying WHO form publication."
                    ),
                ),
                items=[],
            )
        ],
    )


def build_wemwbs_link_only() -> QuestionnaireParent:
    """Add a searchable WEMWBS record while respecting Warwick's no-public-sharing term."""
    return QuestionnaireParent(
        instrument_id="wemwbs",
        name_full="Warwick-Edinburgh Mental Wellbeing Scale",
        construct_ontology=["mental wellbeing"],
        is_commercial=True,
        metadata=QuestionnaireMetadata(
            keywords=["WEMWBS", "wellbeing", "well-being", "mental health"],
            notes=(
                "Metadata-only discovery record. Eligible academic/non-profit organizations "
                "can apply for a non-commercial licence; the licence does not allow public sharing."
            ),
        ),
        versions=[
            QuestionnaireVersion(
                version_id="wemwbs_en_v1",
                language="en",
                locale="en-GB",
                display_name="WEMWBS English (licensed; link-only)",
                publication_year=2007,
                source_citation=(
                    "Tennant et al. (2007). The Warwick-Edinburgh Mental Well-being Scale "
                    "(WEMWBS): development and UK validation."
                ),
                source_doi="10.1186/1477-7525-5-63",
                item_text_included=False,
                source_reported_item_count=14,
                source_reported_dimensions=["mental wellbeing"],
                source_documents=[
                    _source_document(
                        title="WEMWBS licences and pricing",
                        document_type="other",
                        source_url=WEMWBS_LICENSE_URL,
                        license_name="Registration/licence required; no public redistribution",
                        license_url=WEMWBS_NONCOMMERCIAL_URL,
                        redistribution_permitted=False,
                        permission_basis=(
                            "University of Warwick offers an application-based non-commercial "
                            "licence for eligible academic/non-profit organizations, but states "
                            "that it does not permit public sharing or onward provision of WEMWBS."
                        ),
                    )
                ],
                metadata=QuestionnaireMetadata(
                    keywords=["WEMWBS", "Warwick Edinburgh wellbeing"],
                    notes="Request the appropriate licence and retrieve resources from Warwick.",
                ),
                items=[],
            ),
            QuestionnaireVersion(
                version_id="swemwbs_en_v1",
                language="en",
                locale="en-GB",
                display_name="SWEMWBS English short form (licensed; link-only)",
                form_type="short",
                source_citation=(
                    "Short Warwick-Edinburgh Mental Well-being Scale; see the University "
                    "of Warwick licence and resources."
                ),
                item_text_included=False,
                source_reported_item_count=7,
                source_reported_dimensions=["mental wellbeing"],
                source_documents=[
                    _source_document(
                        title="WEMWBS licences and pricing",
                        document_type="other",
                        source_url=WEMWBS_LICENSE_URL,
                        license_name="Registration/licence required; no public redistribution",
                        license_url=WEMWBS_NONCOMMERCIAL_URL,
                        redistribution_permitted=False,
                        permission_basis=(
                            "The University of Warwick licence applies to all WEMWBS forms, "
                            "including SWEMWBS. Eligible non-commercial organisations must "
                            "register; the licence does not permit public sharing or onward use."
                        ),
                    )
                ],
                metadata=QuestionnaireMetadata(
                    keywords=["SWEMWBS", "short Warwick Edinburgh wellbeing"],
                    notes=(
                        "Seven-item short form; use/translation/administration requires the "
                        "appropriate Warwick licence."
                    ),
                ),
                items=[],
            ),
        ],
    )


def build_gse_link_only() -> QuestionnaireParent:
    """Index the 10-item GSE and its language source without assuming rehosting rights."""
    return QuestionnaireParent(
        instrument_id="general_self_efficacy",
        name_full="General Self-Efficacy Scale",
        construct_ontology=["general self-efficacy"],
        is_commercial=None,
        metadata=QuestionnaireMetadata(
            keywords=["GSE", "general self-efficacy", "coping", "wellbeing"],
            notes=(
                "Link-only record. The FU Berlin author site hosts the scale and translations, "
                "but an explicit licence permitting public redistribution of item wording was "
                "not verified in the reviewed pages."
            ),
        ),
        versions=[
            QuestionnaireVersion(
                version_id="gse_en_v1",
                language="en",
                display_name="General Self-Efficacy Scale (English; link-only)",
                publication_year=1995,
                source_citation=(
                    "Schwarzer, R., & Jerusalem, M. (1995). Generalized Self-Efficacy scale. "
                    "In Measures in health psychology: A user's portfolio (pp. 35-37)."
                ),
                item_text_included=False,
                source_reported_item_count=10,
                source_reported_dimensions=["general self-efficacy"],
                target_populations=[
                    TargetPopulation(
                        group_name="General population including adults and adolescents",
                        minimum_age_years=12,
                        notes=(
                            "Author-hosted source says persons below age 12 should not be tested."
                        ),
                    )
                ],
                source_documents=[
                    _source_document(
                        title="General Self-Efficacy Scale English source page",
                        document_type="questionnaire_form",
                        source_url=GSE_ENGLISH_URL,
                        license_name="Use terms not explicit on reviewed source; link only",
                        license_url=GSE_LANGUAGE_URL,
                        redistribution_permitted=False,
                        permission_basis=(
                            "The author-hosted page describes the English form and translations, "
                            "but the reviewed page does not explicitly grant public redistribution "
                            "of item text. This is a catalog rights-status flag, not a use ban."
                        ),
                    )
                ],
                metadata=QuestionnaireMetadata(
                    keywords=["GSE", "10 items", "four-point response"],
                    notes=(
                        "The source reports 10 items, a four-point response scale, and a total "
                        "range of 10-40. Population guidance: intended for adults/adolescents; "
                        "do not administer below age 12 without source review."
                    ),
                ),
                items=[],
            )
        ],
    )


def build_pss_link_only() -> QuestionnaireParent:
    """Index the PSS-10 and PSS-4 and record the source's permission workflow."""
    permission_basis = (
        "Carnegie Mellon directs use-permission requests for the Perceived Stress Scale "
        "through MAPI Research Trust/ePROVIDE. The request is free to submit; approval/use "
        "terms are determined by the rights holder. No item wording is included here."
    )
    license_name = "Permission request via ePROVIDE; public redistribution not established"
    source_document = _source_document(
        title="Perceived Stress Scale forms and permission instructions",
        document_type="questionnaire_form",
        source_url=PSS_SOURCE_URL,
        license_name=license_name,
        license_url="https://eprovide.mapi-trust.org/",
        redistribution_permitted=False,
        permission_basis=permission_basis,
    )
    versions = [
        QuestionnaireVersion(
            version_id="pss10_en_v1",
            language="en",
            display_name="Perceived Stress Scale PSS-10 English (link-only)",
            publication_year=1983,
            source_citation=(
                "Cohen, S., Kamarck, T., & Mermelstein, R. (1983). A global measure of "
                "perceived stress. Journal of Health and Social Behavior, 24(4), 385-396."
            ),
            item_text_included=False,
            source_reported_item_count=10,
            source_reported_dimensions=["perceived stress"],
            source_documents=[source_document],
            metadata=QuestionnaireMetadata(
                keywords=["PSS-10", "perceived stress", "stress"],
                notes=(
                    "The source says the scale has no diagnostic cut-offs; compare within samples."
                ),
            ),
            items=[],
        ),
        QuestionnaireVersion(
            version_id="pss4_en_v1",
            language="en",
            display_name="Perceived Stress Scale PSS-4 English (link-only)",
            form_type="short",
            item_text_included=False,
            source_reported_item_count=4,
            source_reported_dimensions=["perceived stress"],
            source_documents=[source_document],
            metadata=QuestionnaireMetadata(
                keywords=["PSS-4", "short perceived stress scale", "stress"],
                notes=(
                    "Short form indexed separately; exact permission and psychometrics still apply."
                ),
            ),
            items=[],
        ),
    ]
    return QuestionnaireParent(
        instrument_id="perceived_stress_scale",
        name_full="Perceived Stress Scale",
        construct_ontology=["perceived stress"],
        is_commercial=None,
        metadata=QuestionnaireMetadata(
            keywords=["PSS", "Cohen Perceived Stress Scale", "stress"],
            notes=(
                "Link-only. The creator's university page directs requests through ePROVIDE; "
                "a free request is not itself permission to reuse or redistribute the form."
            ),
        ),
        versions=versions,
    )


def write_wellbeing_catalog(output_directory: Path = OUTPUT_DIRECTORY) -> list[Path]:
    """Write validated item-bearing and link-only wellbeing/stress families as JSON."""
    output_directory.mkdir(parents=True, exist_ok=True)
    families = [
        build_rosenberg_self_esteem(),
        build_who5_link_only(),
        build_wemwbs_link_only(),
        build_gse_link_only(),
        build_pss_link_only(),
    ]
    written: list[Path] = []
    for family in families:
        output_path = output_directory / f"{family.instrument_id}.json"
        try:
            output_path.write_text(
                json.dumps(family.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            LOGGER.exception("Could not write wellbeing catalog record to %s", output_path)
            raise
        written.append(output_path)
        LOGGER.info("Wrote %s", output_path)
    return written


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    write_wellbeing_catalog()
