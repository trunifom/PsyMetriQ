# ruff: noqa: E402, E501
"""Build the next high-priority German-relevant instrument references.

The records are metadata-only. They improve discovery while avoiding item-text
reproduction until the exact German edition and reuse terms are verified.
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import (  # noqa: E402
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    TargetPopulation,
)

LOGGER = logging.getLogger(__name__)
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"
SOURCE_ACCESSED_ON = date(2026, 9, 28)


def _family(
    *,
    instrument_id: str,
    name: str,
    construct: list[str],
    source_title: str,
    source_url: str,
    citation: str,
    description: str,
    intended_use: str,
    name_origin: str,
    development_history: str,
    measurement_rationale: str,
    interpretation_notes: str,
    dimensions: list[str],
    keywords: list[str],
    aliases: list[str],
    versions: list[dict[str, object]],
    publication_year: int | None = None,
    doi: str | None = None,
    license_name: str = "Metadata reference; exact German edition and reuse terms require source review",
    license_url: str | None = None,
) -> QuestionnaireParent:
    source = QuestionnaireSourceDocument(
        title=source_title,
        document_type="validation_study",
        language="de",
        source_url=source_url,
        license_name=license_name,
        license_url=license_url,
        redistribution_permitted=False,
        permission_basis=(
            "Only discovery and bibliographic metadata is stored. Item wording and forms are "
            "excluded until the exact German version and reuse terms are verified."
        ),
        accessed_on=SOURCE_ACCESSED_ON,
    )
    family_metadata = QuestionnaireMetadata(
        description=description,
        intended_use=intended_use,
        name_origin=name_origin,
        development_history=development_history,
        measurement_rationale=measurement_rationale,
        interpretation_notes=interpretation_notes,
        keywords=keywords,
        search_aliases=aliases,
        characteristics=["metadata-reference", "German-relevant", "version-specific-evidence"],
    )
    built_versions: list[QuestionnaireVersion] = []
    for spec in versions:
        target_populations = spec.get("target_populations", [])
        built_versions.append(
            QuestionnaireVersion(
                version_id=str(spec["version_id"]),
                language="de",
                locale="de-DE",
                display_name=str(spec["display_name"]),
                form_type=str(spec.get("form_type", "full")),
                publication_year=publication_year,
                source_citation=citation,
                source_doi=doi,
                source_documents=[source],
                item_text_included=False,
                source_reported_item_count=(
                    int(spec["item_count"]) if spec.get("item_count") is not None else None
                ),
                source_reported_dimensions=list(spec.get("dimensions", dimensions)),
                target_populations=list(target_populations),
                metadata=family_metadata,
                items=[],
            )
        )
    return QuestionnaireParent(
        instrument_id=instrument_id,
        name_full=name,
        construct_ontology=construct,
        is_commercial=None,
        metadata=family_metadata,
        versions=built_versions,
    )


def build_priority_catalog() -> list[QuestionnaireParent]:
    adult = [TargetPopulation(group_name="adults", minimum_age_years=18)]
    children_adolescents = [
        TargetPopulation(group_name="children and adolescents", minimum_age_years=3, maximum_age_years=17)
    ]
    adolescent = [TargetPopulation(group_name="adolescents", minimum_age_years=11, maximum_age_years=17)]
    return [
        _family(
            instrument_id="k6_k10",
            name="Kessler Psychological Distress Scale",
            construct=["non-specific psychological distress"],
            source_title="K6/K10 official scale information",
            source_url="https://www.hcp.med.harvard.edu/ncs/k6_scales.php",
            citation="Kessler et al. (2002). Short screening scales to monitor population prevalences and trends in non-specific psychological distress.",
            description="Brief six- and ten-item screens for non-specific psychological distress.",
            intended_use="Population surveys and mental-health screening for general psychological distress.",
            name_origin="K6 and K10 refer to the six- and ten-item Kessler distress forms.",
            development_history="Developed for efficient monitoring of population prevalence and trends in psychological distress.",
            measurement_rationale="Short symptom-frequency questions identify broad distress without assigning a specific disorder.",
            interpretation_notes="Screening thresholds are context-specific and do not establish a diagnosis; use the selected form's scoring guidance.",
            dimensions=["psychological distress"],
            keywords=["K6", "K10", "psychological distress", "psychische Belastung"],
            aliases=["Kessler-6", "Kessler-10", "Kessler Psychological Distress Scale"],
            versions=[
                {"version_id": "k6_de_v1", "display_name": "K6 Deutsch (link-only)", "item_count": 6, "form_type": "screening", "target_populations": adult},
                {"version_id": "k10_de_v1", "display_name": "K10 Deutsch (link-only)", "item_count": 10, "form_type": "screening", "target_populations": adult},
            ],
            publication_year=2002,
        ),
        _family(
            instrument_id="swls",
            name="Satisfaction With Life Scale",
            construct=["life satisfaction"],
            source_title="Satisfaction With Life Scale source publication",
            source_url="https://doi.org/10.1207/s15327752jpa4901_13",
            citation="Diener et al. (1985). The Satisfaction With Life Scale.",
            description="Five-item global measure of cognitive life satisfaction.",
            intended_use="Wellbeing research, social-care evaluation, health research, and population surveys.",
            name_origin="Satisfaction With Life Scale, abbreviated SWLS.",
            development_history="Developed as a brief global judgement of satisfaction with one's life rather than a measure of affect alone.",
            measurement_rationale="Global cognitive evaluation complements symptom and domain-specific wellbeing measures.",
            interpretation_notes="It measures perceived life satisfaction, not objective living conditions or clinical wellbeing; German translation evidence and permission remain version-specific.",
            dimensions=["global life satisfaction"],
            keywords=["SWLS", "life satisfaction", "Lebenszufriedenheit", "wellbeing"],
            aliases=["Satisfaction With Life Scale", "Diener Life Satisfaction Scale"],
            versions=[{"version_id": "swls_de_v1", "display_name": "SWLS Deutsch (link-only)", "item_count": 5, "target_populations": adult}],
            publication_year=1985,
        ),
        _family(
            instrument_id="phq15",
            name="Patient Health Questionnaire-15",
            construct=["somatic symptom severity"],
            source_title="PHQ-15 source publication",
            source_url="https://doi.org/10.1001/archinte.162.10.1049",
            citation="Kroenke, Spitzer, and Williams (2002). The PHQ-15: validity of a new measure for evaluating the severity of somatic symptoms.",
            description="Fifteen-item measure of the severity and burden of common somatic symptoms.",
            intended_use="Primary care, psychosomatic medicine, health research, and screening of somatic symptom burden.",
            name_origin="Patient Health Questionnaire, fifteen-symptom form, abbreviated PHQ-15.",
            development_history="Developed from the somatic symptom module of the Patient Health Questionnaire family.",
            measurement_rationale="A common symptom-burden score supports recognition of somatic distress without assuming a single disease cause.",
            interpretation_notes="A high score is not proof of medically unexplained symptoms or a psychiatric diagnosis; rule out relevant medical causes and use the German version's guidance.",
            dimensions=["somatic symptom burden"],
            keywords=["PHQ-15", "somatic symptoms", "somatische Beschwerden", "primary care"],
            aliases=["Patient Health Questionnaire-15", "PHQ15"],
            versions=[{"version_id": "phq15_de_v1", "display_name": "PHQ-15 Deutsch (link-only)", "item_count": 15, "form_type": "screening", "target_populations": adult}],
            publication_year=2002,
        ),
        _family(
            instrument_id="feess",
            name="Fragebogen zur Erfassung emotionaler und sozialer Schulerfahrungen",
            construct=["school wellbeing", "social integration"],
            source_title="FEESS German school assessment reference",
            source_url="https://www.testzentrale.de/feess.html",
            citation="Rauer and Schuck. FEESS: Fragebogen zur Erfassung emotionaler und sozialer Schulerfahrungen.",
            description="German school questionnaire family for emotional and social experiences in the classroom and school.",
            intended_use="School psychology, educational research, school development, and evaluation of classroom climate.",
            name_origin="FEESS is the German abbreviation for Fragebogen zur Erfassung emotionaler und sozialer Schulerfahrungen.",
            development_history="Developed as age- and grade-appropriate German forms for primary and secondary school contexts.",
            measurement_rationale="School wellbeing and social experience influence participation, learning conditions, and perceived belonging.",
            interpretation_notes="Use the correct grade version and norm tables; results support educational planning and are not diagnostic labels for pupils.",
            dimensions=["classroom climate", "social integration", "school wellbeing"],
            keywords=["FEESS", "Schulerfahrungen", "Klassenklima", "Schulwohlbefinden"],
            aliases=["FEESS 1-2", "FEESS 3-4", "FEESS 5-6", "FEESS 7-10"],
            versions=[{"version_id": "feess_de_v1", "display_name": "FEESS Deutsch (link-only)", "item_count": None, "target_populations": children_adolescents}],
            license_name="Commercial test family; edition and use terms apply",
            license_url="https://www.testzentrale.de/",
        ),
        _family(
            instrument_id="sessko",
            name="Skalen zur Erfassung des schulischen Selbstkonzepts",
            construct=["academic self-concept"],
            source_title="SESSKO German school self-concept reference",
            source_url="https://www.testzentrale.de/sessko.html",
            citation="Schöne et al. (2002). SESSKO: Skalen zur Erfassung des schulischen Selbstkonzepts.",
            description="German questionnaire family for students' academic self-concept and perceived comparison standards.",
            intended_use="Educational research, school counselling, and evaluation of students' academic self-perceptions.",
            name_origin="SESSKO is the German abbreviation for Skalen zur Erfassung des schulischen Selbstkonzepts.",
            development_history="Developed for school-age students with differentiated self-concept dimensions and age-appropriate administration.",
            measurement_rationale="Academic self-concept relates to motivation, learning behavior, and educational choices but is not the same as achievement.",
            interpretation_notes="Interpret with the relevant school level and norm sample; do not treat self-concept scores as objective performance measures.",
            dimensions=["ability self-concept", "social comparison", "individual comparison"],
            keywords=["SESSKO", "schulisches Selbstkonzept", "academic self-concept"],
            aliases=["SESSKO-S", "SESSKO-K"],
            versions=[{"version_id": "sessko_de_v1", "display_name": "SESSKO Deutsch (link-only)", "item_count": None, "target_populations": children_adolescents}],
            license_name="Commercial test family; edition and use terms apply",
            license_url="https://www.testzentrale.de/",
        ),
        _family(
            instrument_id="fas3",
            name="Family Affluence Scale III",
            construct=["family socioeconomic status"],
            source_title="Family Affluence Scale III source publication",
            source_url="https://doi.org/10.1007/s12187-015-9325-3",
            citation="Hartley et al. (2016). Assessing family socioeconomic position through adolescent self-report: the Family Affluence Scale III.",
            description="Adolescent self-report indicator of material family affluence for school and population surveys.",
            intended_use="International school-health surveys and socioeconomic-stratification research with adolescents.",
            name_origin="Family Affluence Scale, third revision, abbreviated FAS III.",
            development_history="Revised to improve cross-national measurement of material family affluence among adolescents.",
            measurement_rationale="Concrete household possessions and conditions can provide a less abstract socioeconomic indicator for adolescents.",
            interpretation_notes="FAS is not a complete measure of socioeconomic status; interpret across time and country carefully and do not substitute it for income or deprivation data.",
            dimensions=["family material affluence"],
            keywords=["FAS III", "Family Affluence Scale", "sozioökonomischer Status", "Jugendliche"],
            aliases=["FAS3", "Family Affluence Scale III"],
            versions=[{"version_id": "fas3_de_v1", "display_name": "Family Affluence Scale III Deutsch (link-only)", "item_count": 6, "form_type": "screening", "target_populations": adolescent}],
            publication_year=2016,
        ),
        _family(
            instrument_id="asrs",
            name="Adult ADHD Self-Report Scale",
            construct=["adult ADHD symptoms"],
            source_title="WHO Adult ADHD Self-Report Scale reference",
            source_url="https://www.hcp.med.harvard.edu/ncs/asrs.php",
            citation="Kessler et al. (2005). The World Health Organization Adult ADHD Self-Report Scale (ASRS).",
            description="Adult self-report screening scale for symptoms associated with attention-deficit/hyperactivity disorder.",
            intended_use="Initial adult ADHD screening in research and clinical pathways, followed by diagnostic assessment.",
            name_origin="Adult ADHD Self-Report Scale, abbreviated ASRS.",
            development_history="Developed through a WHO collaborative process; short and full forms are used in different settings.",
            measurement_rationale="Inattention and hyperactivity/impulsivity symptoms are sampled as a first-stage screen for adult assessment.",
            interpretation_notes="A positive screen is not an ADHD diagnosis; developmental history, impairment, differential diagnosis, and informant evidence are required.",
            dimensions=["inattention", "hyperactivity/impulsivity"],
            keywords=["ASRS", "ADHS", "ADHD", "Aufmerksamkeitsdefizit", "Erwachsene"],
            aliases=["ASRS-v1.1", "ASRS-5", "Adult ADHD Self-Report Scale"],
            versions=[{"version_id": "asrs_de_v1", "display_name": "ASRS Deutsch (link-only)", "item_count": 18, "form_type": "screening", "target_populations": adult}],
            publication_year=2005,
        ),
        _family(
            instrument_id="disyps_fbb_adhs",
            name="DISYPS-III FBB-ADHS",
            construct=["ADHD symptoms in children and adolescents"],
            source_title="DISYPS-III German diagnostic system reference",
            source_url="https://www.testzentrale.de/disyps-iii.html",
            citation="Döpfner and Görtz-Dorten. DISYPS-III: Diagnostik-System für psychische Störungen nach ICD-10 und DSM-5 bei Kindern und Jugendlichen.",
            description="German diagnostic-system reference with observer forms for ADHD symptoms in children and adolescents.",
            intended_use="Multi-informant assessment in child and adolescent clinical, educational, and research settings.",
            name_origin="DISYPS is the German diagnostic system for mental disorders in children and adolescents; FBB-ADHS is its Fremdbeurteilungsbogen for ADHD.",
            development_history="Developed as a German age- and disorder-specific system with parent and teacher assessment forms.",
            measurement_rationale="Combining observer ratings with clinical information helps assess ADHD symptoms across settings and developmental contexts.",
            interpretation_notes="The questionnaire does not replace a full diagnostic process; use the exact DISYPS edition, informant form, norms, and clinical manual.",
            dimensions=["inattention", "hyperactivity", "impulsivity"],
            keywords=["DISYPS", "FBB-ADHS", "ADHS", "Kinder", "Jugendliche"],
            aliases=["DISYPS-III", "FBB-ADHS", "SBB-ADHS"],
            versions=[{"version_id": "disyps_fbb_adhs_de_v1", "display_name": "DISYPS-III FBB-ADHS Deutsch (link-only)", "item_count": None, "target_populations": children_adolescents}],
            license_name="Commercial diagnostic system; edition and use terms apply",
            license_url="https://www.testzentrale.de/",
        ),
        _family(
            instrument_id="conners3",
            name="Conners 3",
            construct=["ADHD and related behavioral symptoms"],
            source_title="Conners 3 German reference",
            source_url="https://www.testzentrale.de/conners-3.html",
            citation="Conners 3 German edition; commercial multi-informant ADHD and behavior assessment.",
            description="Multi-informant rating-scale family for ADHD symptoms, executive difficulties, and related behavior in children and adolescents.",
            intended_use="Clinical and educational assessment using parent, teacher, and self-report perspectives.",
            name_origin="Conners 3 is the third edition of the Conners behavior-rating family.",
            development_history="Maintained as an age- and informant-specific rating-scale system with multiple forms.",
            measurement_rationale="Cross-informant ratings capture behavior across home and school contexts and support hypothesis generation.",
            interpretation_notes="Commercial norms and clinical interpretation are edition-specific; ratings alone do not establish an ADHD diagnosis.",
            dimensions=["inattention", "hyperactivity/impulsivity", "executive functioning", "behavioral problems"],
            keywords=["Conners 3", "ADHS", "ADHD", "Verhaltensbeurteilung"],
            aliases=["Conners-3", "Conners Rating Scales"],
            versions=[{"version_id": "conners3_de_v1", "display_name": "Conners 3 Deutsch (link-only)", "item_count": None, "target_populations": children_adolescents}],
            license_name="Commercial test family; edition and use terms apply",
            license_url="https://www.testzentrale.de/",
        ),
        _family(
            instrument_id="aq",
            name="Autism-Spectrum Quotient",
            construct=["autistic traits"],
            source_title="Autism-Spectrum Quotient source publication",
            source_url="https://doi.org/10.1080/026404101300117134",
            citation="Baron-Cohen et al. (2001). The Autism-Spectrum Quotient (AQ): evidence from Asperger syndrome/high-functioning autism, males and females, scientists and mathematicians.",
            description="Self-report screening questionnaire for autistic traits in adolescents and adults with average or above-average intelligence.",
            intended_use="Research and initial autism-trait screening; not a diagnostic assessment.",
            name_origin="Autism-Spectrum Quotient, abbreviated AQ.",
            development_history="Developed as a dimensional self-report measure of autistic traits in adults and adolescents.",
            measurement_rationale="Social skills, attention switching, attention to detail, communication, and imagination represent different trait domains.",
            interpretation_notes="Cutoffs are screening aids and vary with population; German translation quality and diagnostic follow-up must be considered.",
            dimensions=["social skills", "attention switching", "attention to detail", "communication", "imagination"],
            keywords=["AQ", "Autism-Spectrum Quotient", "Autismus", "ASS"],
            aliases=["Autism Quotient", "AQ-50"],
            versions=[{"version_id": "aq_de_v1", "display_name": "Autism-Spectrum Quotient Deutsch (link-only)", "item_count": 50, "form_type": "screening", "target_populations": adolescent}],
            publication_year=2001,
        ),
        _family(
            instrument_id="srs2",
            name="Social Responsiveness Scale-2",
            construct=["social communication and autistic social traits"],
            source_title="SRS-2 German reference",
            source_url="https://www.testzentrale.de/social-responsiveness-scale-2.html",
            citation="SRS-2 German edition; social-responsiveness rating scale family.",
            description="Rating-scale family for social communication, restricted interests, and social responsiveness across development.",
            intended_use="Clinical, educational, and research assessment of social functioning and autism-related traits.",
            name_origin="Social Responsiveness Scale, second edition, abbreviated SRS-2.",
            development_history="Developed as a multi-informant scale with age- and informant-specific forms.",
            measurement_rationale="Social communication and repetitive/restricted behavior are rated dimensionally across everyday contexts.",
            interpretation_notes="SRS-2 scores are not sufficient for an autism diagnosis and can be influenced by language, ADHD, anxiety, and other conditions.",
            dimensions=["social awareness", "social cognition", "social communication", "social motivation", "restricted interests and repetitive behavior"],
            keywords=["SRS-2", "Autismus", "ASS", "soziale Responsivität"],
            aliases=["Social Responsiveness Scale", "SRS II"],
            versions=[{"version_id": "srs2_de_v1", "display_name": "SRS-2 Deutsch (link-only)", "item_count": None, "target_populations": children_adolescents}],
            license_name="Commercial test family; edition and use terms apply",
            license_url="https://www.testzentrale.de/",
        ),
        _family(
            instrument_id="mchat_rf",
            name="Modified Checklist for Autism in Toddlers, Revised with Follow-Up",
            construct=["early autism risk"],
            source_title="M-CHAT-R/F official screening resources",
            source_url="https://www.mchatscreen.com/",
            citation="Robins et al. (2014). Validation of the Modified Checklist for Autism in Toddlers, Revised with Follow-up.",
            description="Two-stage parent-report screening tool for autism risk in toddlers.",
            intended_use="Early screening and follow-up referral for toddlers approximately 16-30 months old.",
            name_origin="Modified Checklist for Autism in Toddlers, Revised with Follow-Up, abbreviated M-CHAT-R/F.",
            development_history="Revised the original M-CHAT and added a structured follow-up interview to reduce false-positive screens.",
            measurement_rationale="Early parent-observed social-communication and behavior indicators can support timely developmental evaluation.",
            interpretation_notes="A positive screen indicates need for follow-up or developmental evaluation, not autism diagnosis; use the official German form and process.",
            dimensions=["social communication", "early behavior indicators"],
            keywords=["M-CHAT-R/F", "Autismus", "ASS", "Kleinkinder", "Früherkennung"],
            aliases=["M-CHAT", "Modified Checklist for Autism in Toddlers"],
            doi="10.1177/1362361315605763",
            publication_year=2014,
            versions=[{"version_id": "mchat_rf_de_v1", "display_name": "M-CHAT-R/F Deutsch (link-only)", "item_count": 20, "form_type": "screening", "target_populations": [TargetPopulation(group_name="toddlers", minimum_age_years=1, maximum_age_years=3)]}],
            license_name="Official screening form; exact language and use terms apply",
            license_url="https://www.mchatscreen.com/",
        ),
        _family(
            instrument_id="copsoq",
            name="Copenhagen Psychosocial Questionnaire",
            construct=["psychosocial working conditions"],
            source_title="COPSOQ German source and questionnaire information",
            source_url="https://www.copsoq.de/",
            citation="Kristensen et al. (2005). The Copenhagen Psychosocial Questionnaire: a tool for the assessment and improvement of the psychosocial work environment.",
            description="Questionnaire family for psychosocial working conditions, demands, resources, leadership, and wellbeing.",
            intended_use="Occupational health, organizational development, employee surveys, and psychosocial risk assessment.",
            name_origin="Copenhagen Psychosocial Questionnaire, abbreviated COPSOQ.",
            development_history="Developed as a multidimensional occupational-health questionnaire and adapted for national versions including German use.",
            measurement_rationale="Work demands, influence, social relations, leadership, and health-related outcomes interact in psychosocial work environments.",
            interpretation_notes="Use the selected German COPSOQ version and benchmark guidance; results describe working conditions and do not diagnose individual mental disorders.",
            dimensions=["work demands", "influence", "social relations", "leadership", "health and wellbeing"],
            keywords=["COPSOQ", "Arbeitsstress", "psychosoziale Belastung", "Arbeitsbedingungen"],
            aliases=["Copenhagen Psychosocial Questionnaire"],
            doi="10.1080/02678370500089585",
            publication_year=2005,
            versions=[{"version_id": "copsoq_de_v1", "display_name": "COPSOQ Deutsch (link-only)", "item_count": None, "target_populations": adult}],
            license_url="https://www.copsoq.de/",
        ),
        _family(
            instrument_id="eri",
            name="Effort-Reward Imbalance Questionnaire",
            construct=["occupational stress", "effort-reward imbalance"],
            source_title="Effort-Reward Imbalance source publication",
            source_url="https://doi.org/10.1093/oxfordjournals.aje.a009376",
            citation="Siegrist (1996). Adverse health effects of high-effort/low-reward conditions.",
            description="Occupational-stress questionnaire on work effort, rewards, and overcommitment.",
            intended_use="Occupational health, work-stress research, and psychosocial risk assessment.",
            name_origin="Effort-Reward Imbalance model and questionnaire, abbreviated ERI.",
            development_history="Developed from the sociological effort-reward imbalance model of work stress.",
            measurement_rationale="Stress risk increases when high effort is not matched by adequate esteem, salary, promotion, or job security.",
            interpretation_notes="Use the exact German form and ratio/scoring rules; it describes work conditions and does not diagnose burnout or depression.",
            dimensions=["effort", "reward", "overcommitment"],
            keywords=["ERI", "Effort-Reward Imbalance", "Arbeitsstress", "Verausgabung-Belohnung"],
            aliases=["Siegrist ERI", "Effort Reward Imbalance Questionnaire"],
            publication_year=1996,
            versions=[{"version_id": "eri_de_v1", "display_name": "ERI Deutsch (link-only)", "item_count": None, "target_populations": adult}],
        ),
        _family(
            instrument_id="olbi",
            name="Oldenburg Burnout Inventory",
            construct=["burnout", "occupational exhaustion"],
            source_title="Oldenburg Burnout Inventory source publication",
            source_url="https://doi.org/10.1037/0021-9010.88.3.499",
            citation="Demerouti et al. (2003). The convergent validity of two burnout instruments.",
            description="Questionnaire measuring occupational exhaustion and disengagement as burnout-related dimensions.",
            intended_use="Occupational-health research, organizational surveys, and burnout-related assessment.",
            name_origin="Oldenburg Burnout Inventory, abbreviated OLBI.",
            development_history="Developed as an alternative burnout measure with positively and negatively worded exhaustion and disengagement items.",
            measurement_rationale="Burnout-related strain includes both depletion of energy and psychological distancing from work.",
            interpretation_notes="Use the validated German version and scoring; the OLBI is not a standalone clinical diagnosis and context affects interpretation.",
            dimensions=["exhaustion", "disengagement"],
            keywords=["OLBI", "Burnout", "Erschöpfung", "Arbeitsdistanzierung"],
            aliases=["Oldenburg Burnout Inventory"],
            publication_year=2003,
            versions=[{"version_id": "olbi_de_v1", "display_name": "OLBI Deutsch (link-only)", "item_count": 16, "target_populations": adult}],
        ),
    ]


def write_priority_catalog(output_directory: Path = OUTPUT_DIRECTORY) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for family in build_priority_catalog():
        path = output_directory / f"{family.instrument_id}.json"
        path.write_text(family.model_dump_json(indent=2), encoding="utf-8")
        paths.append(path)
        LOGGER.info("Wrote %s with %d variants", path, len(family.versions))
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    write_priority_catalog()
