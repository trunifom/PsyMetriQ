# ruff: noqa: E402, E501
"""Build additional German-relevant, metadata-only instrument references.

These records improve discovery without copying questionnaire wording. Rights are
kept explicit per source and must be reviewed before administration or reuse.
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (
    QuestionnaireContributor,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    TargetPopulation,
)

LOGGER = logging.getLogger(__name__)
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"
SOURCE_ACCESSED_ON = date(2026, 9, 28)


def _source(
    *,
    title: str,
    source_url: str,
    citation: str,
    license_name: str = "Metadata reference; exact reuse terms require source review",
    license_url: str | None = None,
) -> QuestionnaireSourceDocument:
    return QuestionnaireSourceDocument(
        title=title,
        document_type="validation_study",
        language="de",
        source_url=source_url,
        license_name=license_name,
        license_url=license_url,
        redistribution_permitted=False,
        permission_basis=(
            "Only bibliographic and discovery metadata is stored. Questionnaire wording and "
            "forms are not included until exact edition, language, and reuse terms are verified."
        ),
        accessed_on=SOURCE_ACCESSED_ON,
    )


def _version(
    *,
    version_id: str,
    display_name: str,
    source_documents: list[QuestionnaireSourceDocument],
    source_reported_item_count: int | None,
    dimensions: list[str],
    description: str,
    intended_use: str,
    name_origin: str,
    development_history: str,
    measurement_rationale: str,
    interpretation_notes: str,
    citation: str | None = None,
    doi: str | None = None,
    publication_year: int | None = None,
    target_populations: list[TargetPopulation] | None = None,
    form_type: str = "full",
    keywords: list[str] | None = None,
    characteristics: list[str] | None = None,
) -> QuestionnaireVersion:
    return QuestionnaireVersion(
        version_id=version_id,
        language="de",
        locale="de-DE",
        display_name=display_name,
        form_type=form_type,
        target_populations=target_populations or [],
        publication_year=publication_year or (2008 if citation and "KIDSCREEN" in citation else None),
        source_citation=citation,
        source_doi=doi,
        source_documents=source_documents,
        item_text_included=False,
        source_reported_item_count=source_reported_item_count,
        source_reported_dimensions=dimensions,
        metadata=QuestionnaireMetadata(
            description=description,
            intended_use=intended_use,
            name_origin=name_origin,
            development_history=development_history,
            measurement_rationale=measurement_rationale,
            interpretation_notes=interpretation_notes,
            keywords=keywords or [],
            characteristics=characteristics or ["metadata-reference", "German-source-evidence"],
        ),
        items=[],
    )


def build_kidscreen() -> QuestionnaireParent:
    official_url = "https://www.kidscreen.org/english/questionnaires/"
    citation = (
        "Ravens-Sieberer U et al. The KIDSCREEN-52 quality of life measure for children and "
        "adolescents: psychometric results from a cross-cultural survey in 13 European countries. "
        "Value in Health. 2008;11(4):645-658."
    )
    source = _source(
        title="KIDSCREEN official questionnaire information",
        source_url=official_url,
        citation=citation,
        license_name="Official site states fully open access; verify exact download terms",
        license_url=official_url,
    )
    common = dict(
        source_documents=[source],
        target_populations=[
            TargetPopulation(
                group_name="children and adolescents",
                minimum_age_years=8,
                maximum_age_years=18,
                notes="Official KIDSCREEN population; self-report and parent proxy versions exist.",
            )
        ],
        dimensions=["health-related quality of life", "psychological wellbeing", "social wellbeing"],
        description="Health-related quality-of-life assessment for children and adolescents aged 8-18.",
        intended_use="Screening, monitoring, evaluation, and health-survey research in school or health settings.",
        name_origin="KIDSCREEN is the name of the European child and adolescent health-related quality-of-life project.",
        development_history="Developed simultaneously in 13 European countries with cross-cultural translation and adaptation.",
        measurement_rationale="Separate physical, psychological, social, and school-related wellbeing dimensions describe subjective health-related quality of life.",
        interpretation_notes="The official site reports version-specific internal consistency and norm information; use the selected version and country guidance.",
        citation=citation,
        doi="10.1111/j.1524-4733.2007.00291.x",
        keywords=["KIDSCREEN", "quality of life", "children", "adolescents", "HRQoL"],
        characteristics=["self-report", "parent-proxy-available", "German-version-available", "metadata-reference"],
    )
    return QuestionnaireParent(
        instrument_id="kidscreen",
        name_full="KIDSCREEN Health-Related Quality of Life",
        construct_ontology=["child and adolescent health-related quality of life"],
        is_commercial=None,
        contributors=[QuestionnaireContributor(name="KIDSCREEN Group", role="author")],
        metadata=QuestionnaireMetadata(
            description="European family of health-related quality-of-life questionnaires for children and adolescents.",
            intended_use="Cross-cultural health and wellbeing assessment in children and adolescents.",
            name_origin="KIDSCREEN names the European child and adolescent quality-of-life project.",
            development_history="Developed collaboratively across 13 European countries.",
            measurement_rationale="A multidimensional profile captures subjective physical, psychological, and social wellbeing.",
            interpretation_notes="KIDSCREEN-52, KIDSCREEN-27, and KIDSCREEN-10 are different forms and must use their own scoring and norms.",
            keywords=["KIDSCREEN", "children", "adolescents", "quality of life", "Lebensqualität"],
            search_aliases=["KIDSCREEN-52", "KIDSCREEN-27", "KIDSCREEN-10"],
        ),
        versions=[
            _version(version_id="kidscreen_52_de_v1", display_name="KIDSCREEN-52 Deutsch (link-only)", source_reported_item_count=52, form_type="full", **common),
            _version(version_id="kidscreen_27_de_v1", display_name="KIDSCREEN-27 Deutsch (link-only)", source_reported_item_count=27, form_type="short", **common),
            _version(version_id="kidscreen_10_de_v1", display_name="KIDSCREEN-10 Index Deutsch (link-only)", source_reported_item_count=10, form_type="short", **common),
        ],
    )


def build_mspss() -> QuestionnaireParent:
    source_url = "https://doi.org/10.1111/opn.12540"
    source = _source(title="German psychometric evidence for MSPSS in older adults", source_url=source_url, citation="Boggatz. German psychometric evidence for the Multidimensional Scale of Perceived Social Support in older adults.")
    version = _version(
        version_id="mspss_de_v1",
        display_name="Multidimensional Scale of Perceived Social Support Deutsch (link-only)",
        source_documents=[source],
        source_reported_item_count=12,
        dimensions=["family support", "friend support", "significant-other support"],
        description="Twelve-item measure of perceived support from family, friends, and a significant other.",
        intended_use="Research and social-support assessment; the German evidence in this record includes older-adult psychometrics.",
        name_origin="Multidimensional Scale of Perceived Social Support, abbreviated MSPSS.",
        development_history="Originally introduced by Zimet and colleagues in 1988; German population evidence must be kept version-specific.",
        measurement_rationale="Three support-source dimensions distinguish perceived availability of different social relationships.",
        interpretation_notes="Perceived support is not identical to network size or objectively received support; use German validation evidence for the target population.",
        citation="Zimet et al. (1988). The Multidimensional Scale of Perceived Social Support.",
        doi="10.1207/s15327752jpa5201_2",
        keywords=["MSPSS", "social support", "soziale Unterstützung"],
        characteristics=["self-report", "German-validation-evidence", "metadata-reference"],
    )
    return QuestionnaireParent(
        instrument_id="mspss",
        name_full="Multidimensional Scale of Perceived Social Support",
        construct_ontology=["perceived social support"],
        metadata=version.metadata,
        versions=[version],
    )


def build_cius() -> QuestionnaireParent:
    source = _source(title="German adolescent CIUS validation", source_url="https://doi.org/10.1089/cyber.2012.0689", citation="Barke et al. (2013). The German version of the Compulsive Internet Use Scale.")
    version = _version(
        version_id="cius_de_v1", display_name="Compulsive Internet Use Scale Deutsch (link-only)", source_documents=[source], source_reported_item_count=14, dimensions=["compulsive internet use", "loss of control", "negative consequences"], description="Fourteen-item measure of problematic or compulsive internet use.", intended_use="Research screening and behavioral-health studies of problematic internet use.", name_origin="Compulsive Internet Use Scale, abbreviated CIUS.", development_history="The German adolescent version was evaluated in a validation study; adult language-invariance evidence is documented separately in the literature.", measurement_rationale="Items cover loss of control, preoccupation, withdrawal-like experiences, conflict, and negative consequences.", interpretation_notes="A screening score is not a diagnosis; do not transfer adolescent cutoffs or translation evidence automatically to adults.", citation="Meerkerk et al. (2009). The Compulsive Internet Use Scale.", doi="10.1089/cpb.2008.0181", keywords=["CIUS", "problematic internet use", "Internetnutzung"], characteristics=["self-report", "German-adolescent-validation", "metadata-reference"],
    )
    return QuestionnaireParent(instrument_id="cius", name_full="Compulsive Internet Use Scale", construct_ontology=["problematic internet use"], metadata=version.metadata, versions=[version])


def build_gadis_a() -> QuestionnaireParent:
    source = _source(title="German Gaming Disorder Scale for Adolescents validation", source_url="https://doi.org/10.3390/jcm9040993", citation="Paschke et al. (2020). German Gaming Disorder Scale for Adolescents (GADIS-A).")
    version = _version(
        version_id="gadis_a_de_v1", display_name="Gaming Disorder Scale for Adolescents Deutsch (link-only)", source_documents=[source], source_reported_item_count=None, dimensions=["gaming disorder symptoms", "impaired control", "functional impairment"], description="German adolescent screening instrument for gaming-disorder symptoms based on ICD-11 concepts.", intended_use="Research screening among adolescents with frequent gaming; not a standalone clinical diagnosis.", name_origin="Gaming Disorder Scale for Adolescents, abbreviated GADIS-A.", development_history="Validated in German frequent-gamer samples aged 10-17 in an ICD-11-oriented study.", measurement_rationale="The instrument targets impaired control and clinically relevant functional impairment associated with gaming.", interpretation_notes="ICD-11 gaming disorder concepts are not interchangeable with DSM-5 internet-gaming-disorder criteria; use the exact manual and population evidence.", citation="Paschke et al. (2020). Psychometric properties of the Gaming Disorder Scale for Adolescents.", doi="10.3390/jcm9040993", keywords=["GADIS-A", "gaming disorder", "gaming", "Jugendliche"], characteristics=["self-report", "adolescent-form", "German-validation", "metadata-reference"], target_populations=[TargetPopulation(group_name="adolescents and frequent gamers", minimum_age_years=10, maximum_age_years=17)],
    )
    return QuestionnaireParent(instrument_id="gadis_a", name_full="Gaming Disorder Scale for Adolescents", construct_ontology=["gaming disorder"], metadata=version.metadata, versions=[version])


def build_isap() -> QuestionnaireParent:
    source = _source(title="German ISAP school attendance problems validation", source_url="https://doi.org/10.1007/s00787-018-1204-2", citation="Knollmann, Reissner, and Hebebrand (2019). ISAP validation in children and adolescents.")
    version = _version(
        version_id="isap_de_v1", display_name="Inventar zur Erfassung von Schulabsentismus Deutsch (link-only)", source_documents=[source], source_reported_item_count=None, dimensions=["school attendance problems", "school refusal", "school-related distress"], description="German instrument for assessing school-attendance problems and related functional patterns.", intended_use="Clinical and research assessment of school absenteeism and school-refusal-related problems in young people.", name_origin="ISAP is the German acronym for Inventar zur Erfassung von Schulabsentismus.", development_history="Developed and evaluated in German child and adolescent clinical research; the parent form ISAP-P is a distinct version.", measurement_rationale="Differentiating attendance problems and their maintaining contexts supports assessment alongside objective attendance records.", interpretation_notes="The instrument should not replace attendance records or clinical assessment; parent-form evidence has documented limitations and must be interpreted separately.", citation="Knollmann et al. (2019). School absenteeism and the ISAP instrument.", doi="10.1007/s00787-018-1204-2", keywords=["ISAP", "Schulabsentismus", "school attendance", "school refusal"], characteristics=["German-development", "clinical-youth-evidence", "metadata-reference"],
    )
    return QuestionnaireParent(instrument_id="isap", name_full="Inventar zur Erfassung von Schulabsentismus", construct_ontology=["school attendance problems"], metadata=version.metadata, versions=[version])


def build_psq() -> QuestionnaireParent:
    source = _source(
        title="German psychometric evidence for the Perceived Stress Questionnaire",
        source_url="https://doi.org/10.1097/01.psy.0000151491.80157.07",
        citation="Fliege et al. (2005). The Perceived Stress Questionnaire (PSQ) reconsidered.",
    )
    version = _version(
        version_id="psq_de_v1",
        display_name="Perceived Stress Questionnaire Deutsch (link-only)",
        source_documents=[source],
        source_reported_item_count=30,
        dimensions=["worries", "tension", "demands", "joy"],
        description="Thirty-item self-report measure of perceived stress and related positive and negative experiences.",
        intended_use="Research and health-related assessment of perceived stress, including clinical and non-clinical samples.",
        name_origin="Perceived Stress Questionnaire, abbreviated PSQ.",
        development_history="The PSQ was introduced as a multidimensional stress measure and later evaluated in German samples with reference values.",
        measurement_rationale="Separating worries, tension, demands, and joy captures subjective stress appraisal more broadly than an event count.",
        interpretation_notes="Use the exact German form and scoring instructions; scores describe perceived stress and are not diagnostic cutoffs.",
        citation="Fliege et al. (2005). The Perceived Stress Questionnaire (PSQ) reconsidered: validation and reference values from different clinical and healthy populations.",
        doi="10.1097/01.psy.0000151491.80157.07",
        publication_year=2005,
        keywords=["PSQ", "perceived stress", "wahrgenommener Stress", "Belastung"],
        characteristics=["self-report", "multidimensional-stress", "German-validation", "metadata-reference"],
    )
    return QuestionnaireParent(
        instrument_id="psq",
        name_full="Perceived Stress Questionnaire",
        construct_ontology=["perceived stress"],
        metadata=version.metadata,
        versions=[version],
    )


def build_f_sozu() -> QuestionnaireParent:
    source = _source(
        title="Fragebogen zur sozialen Unterstützung (F-SozU)",
        source_url="https://www.testzentrale.de/fragebogen-zur-sozialen-unterstuetzung.html",
        citation="Fydrich, Sommer, and Brähler. Fragebogen zur sozialen Unterstützung (F-SozU).",
    )
    version = _version(
        version_id="f_sozu_k14_de_v1",
        display_name="F-SozU K-14 Deutsch (link-only)",
        source_documents=[source],
        source_reported_item_count=14,
        dimensions=["emotional support", "practical support", "social integration"],
        description="German short questionnaire on perceived social support and social integration.",
        intended_use="Research, psychosocial counselling, rehabilitation, and social-work assessment of perceived support.",
        name_origin="F-SozU is the German abbreviation for Fragebogen zur sozialen Unterstützung.",
        development_history="Developed as a German family of social-support questionnaires with longer and shorter forms; the K-14 form is represented here separately.",
        measurement_rationale="Perceived emotional, practical, and integrative support are distinct resources relevant to coping and participation.",
        interpretation_notes="Perceived support is not the same as objective network size or received help; use the exact form manual and target-population evidence.",
        citation="Fydrich et al. (2007). Fragebogen zur sozialen Unterstützung (F-SozU K-14/K-22).",
        keywords=["F-SozU", "soziale Unterstützung", "social support", "Sozialarbeit"],
        characteristics=["self-report", "German-instrument", "social-work-relevant", "metadata-reference"],
    )
    return QuestionnaireParent(
        instrument_id="f_sozu",
        name_full="Fragebogen zur sozialen Unterstützung",
        construct_ontology=["perceived social support"],
        metadata=version.metadata,
        versions=[version],
    )


def build_ucla_loneliness() -> QuestionnaireParent:
    source = _source(
        title="UCLA Loneliness Scale short-form source and German-use reference",
        source_url="https://doi.org/10.1177/0164027504268574",
        citation="Hughes et al. (2004). A short scale for measuring loneliness in large surveys.",
    )
    version = _version(
        version_id="ucla_loneliness_3_de_v1",
        display_name="UCLA Loneliness Scale Kurzform Deutsch (link-only)",
        source_documents=[source],
        source_reported_item_count=3,
        dimensions=["loneliness", "social isolation"],
        description="Three-item short measure of subjective loneliness suitable for large surveys.",
        intended_use="Population research and social-work screening for perceived loneliness; German translation evidence must be checked for the selected wording.",
        name_origin="UCLA Loneliness Scale, developed at the University of California, Los Angeles; this record represents the three-item short form.",
        development_history="The three-item version was developed for large population surveys from the longer UCLA loneliness scale family.",
        measurement_rationale="Subjective loneliness reflects perceived lack of meaningful connection and is distinct from the number of social contacts.",
        interpretation_notes="A short score is not a clinical diagnosis; German-language use does not by itself establish translation equivalence or permission to reproduce items.",
        citation="Hughes et al. (2004). A short scale for measuring loneliness in large surveys.",
        doi="10.1177/0164027504268574",
        publication_year=2004,
        keywords=["UCLA Loneliness", "Einsamkeit", "social isolation", "soziale Isolation"],
        characteristics=["self-report", "short-form", "German-use-reference", "metadata-reference"],
    )
    return QuestionnaireParent(
        instrument_id="ucla_loneliness",
        name_full="UCLA Loneliness Scale",
        construct_ontology=["loneliness"],
        metadata=version.metadata,
        versions=[version],
    )


def build_sdq() -> QuestionnaireParent:
    source = _source(
        title="Strengths and Difficulties Questionnaire official forms and German versions",
        source_url="https://www.sdqinfo.org/py/sdqinfo/b0.py",
        citation="Goodman (2001). Psychometric properties of the strengths and difficulties questionnaire.",
        license_name="Official forms available; copyright and version-specific use terms apply",
        license_url="https://www.sdqinfo.org/py/sdqinfo/c0.py",
    )
    common = dict(
        source_documents=[source],
        source_reported_item_count=25,
        dimensions=["emotional symptoms", "conduct problems", "hyperactivity", "peer problems", "prosocial behavior"],
        description="Twenty-five-item behavioral screening questionnaire with five strengths and difficulties domains.",
        intended_use="Child and adolescent mental-health, school, pediatric, and social-work screening with multiple informants.",
        name_origin="Strengths and Difficulties Questionnaire, abbreviated SDQ.",
        development_history="Developed as a brief multi-informant behavioral screening family with parent, teacher, and self-report forms.",
        measurement_rationale="Combining difficulty domains with prosocial behavior gives a balanced profile of emotional, behavioral, attentional, peer, and strength-related functioning.",
        interpretation_notes="Screening bands are not diagnoses; compare the informant, age band, language version, and local manual. Impact supplements are separate from the 25 core items.",
        citation="Goodman (2001). Psychometric properties of the strengths and difficulties questionnaire.",
        doi="10.1037/1040-3590.13.3.367",
        publication_year=2001,
        keywords=["SDQ", "Strengths and Difficulties Questionnaire", "Verhaltensscreening", "Kinder", "Jugendliche"],
        characteristics=["multi-informant", "German-version-available", "school-relevant", "metadata-reference"],
    )
    versions = [
        _version(version_id="sdq_parent_de_v1", display_name="SDQ Elternversion Deutsch (link-only)", target_populations=[TargetPopulation(group_name="children and adolescents", minimum_age_years=2, maximum_age_years=17)], **common),
        _version(version_id="sdq_teacher_de_v1", display_name="SDQ Lehrkraftversion Deutsch (link-only)", target_populations=[TargetPopulation(group_name="children and adolescents", minimum_age_years=2, maximum_age_years=17)], **common),
        _version(version_id="sdq_self_de_v1", display_name="SDQ Selbstbericht Deutsch (link-only)", target_populations=[TargetPopulation(group_name="adolescents", minimum_age_years=11, maximum_age_years=17)], **common),
    ]
    return QuestionnaireParent(
        instrument_id="sdq",
        name_full="Strengths and Difficulties Questionnaire",
        construct_ontology=["child and adolescent mental health"],
        metadata=versions[0].metadata,
        versions=versions,
    )


def build_additional_catalog() -> list[QuestionnaireParent]:
    return [
        build_kidscreen(),
        build_mspss(),
        build_cius(),
        build_gadis_a(),
        build_isap(),
        build_psq(),
        build_f_sozu(),
        build_ucla_loneliness(),
        build_sdq(),
    ]


def write_additional_catalog(output_directory: Path = OUTPUT_DIRECTORY) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for family in build_additional_catalog():
        path = output_directory / f"{family.instrument_id}.json"
        path.write_text(family.model_dump_json(indent=2), encoding="utf-8")
        paths.append(path)
        LOGGER.info("Wrote %s with %d variants", path, len(family.versions))
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    write_additional_catalog()
