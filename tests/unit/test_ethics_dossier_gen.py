from datetime import date

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireContributor,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    ResponseOption,
    TargetPopulation,
)
from src.exporters.ethics_dossier_gen import EthicsDossierError, build_ethics_dossier


def _documented_family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        locale="en-US",
        administration_time="ca. 5-10 Minuten",
        publication_year=1999,
        source_citation="Example, A. (1999). The Example Scale.",
        source_doi="10.1000/example",
        psychometric_summary="Cronbach's alpha reported around .85 in the original sample.",
        cosmin_metrics={"cronbach_alpha": "0.85 (original validation sample)"},
        target_populations=[
            TargetPopulation(group_name="Adults", minimum_age_years=18, maximum_age_years=65)
        ],
        source_documents=[
            QuestionnaireSourceDocument(
                title="Example Scale Manual",
                document_type="questionnaire_form",
                language="en",
                source_url="https://example.org/scale.pdf",
                license_name="CC BY 4.0",
                redistribution_permitted=True,
                permission_basis="Official public-domain notice",
                accessed_on=date(2024, 1, 1),
            )
        ],
        response_sets={"freq": [ResponseOption(code=0, label="Never", score=0)]},
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Item one",
                response_set_ref="freq",
            ),
            ItemSchema(
                item_id="q2",
                variable_name="q2",
                dimension="core",
                prompt_text="Item two",
                response_set_ref="freq",
            ),
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo",
        name_full="Demo Instrument",
        is_commercial=False,
        contributors=[QuestionnaireContributor(name="A. Example", role="author")],
        versions=[version],
    )


def _reference_family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1", language="en", item_text_included=False, is_commercial=None
    )
    return QuestionnaireParent(
        instrument_id="ref",
        name_full="Reference Instrument",
        is_commercial=None,
        versions=[version],
    )


def test_build_ethics_dossier_rejects_an_empty_selection() -> None:
    try:
        build_ethics_dossier([])
    except EthicsDossierError:
        pass
    else:
        raise AssertionError("expected EthicsDossierError")


def test_build_ethics_dossier_includes_documented_fields() -> None:
    family = _documented_family()

    dossier = build_ethics_dossier(
        [(family, family.versions[0], [])],
        project_name="Wellbeing Study",
        project_description="A cross-sectional survey of adult wellbeing.",
        generated_on=date(2026, 9, 29),
    )

    assert "Fragebogenbatterie" in dossier
    assert "Wellbeing Study" in dossier
    assert "A cross-sectional survey of adult wellbeing." in dossier
    assert "Demo Instrument" in dossier
    assert "ca. 5–10 Minuten" in dossier or "ca. 5-10 Minuten" in dossier
    assert "CC BY 4.0" in dossier
    assert "Example, A. (1999)" in dossier
    assert "10.1000/example" in dossier
    assert "Adults, 18-65 Jahre" in dossier
    assert "cronbach_alpha" in dossier
    # The disclaimer legitimately quotes the phrase; no *field* should render it here.
    assert dossier.count("Nicht dokumentiert") == 1


def test_build_ethics_dossier_marks_missing_fields_as_not_documented() -> None:
    family = _reference_family()

    dossier = build_ethics_dossier([(family, family.versions[0], [])])

    assert dossier.count("Nicht dokumentiert") >= 3
    assert "Metadatenreferenz" in dossier


def test_build_ethics_dossier_reports_the_selected_item_subset() -> None:
    family = _documented_family()

    dossier = build_ethics_dossier([(family, family.versions[0], ["q1"])])

    assert "1 ausgewählt von 2" in dossier


def test_build_ethics_dossier_always_carries_the_planning_aid_disclaimer() -> None:
    family = _documented_family()

    dossier = build_ethics_dossier([(family, family.versions[0], [])])

    assert "Planungshilfe" in dossier
    assert "keine Rechts- oder Ethikberatung" in dossier


def test_build_ethics_dossier_sums_total_battery_time_across_instruments() -> None:
    family = _documented_family()

    dossier = build_ethics_dossier(
        [(family, family.versions[0], []), (family, family.versions[0], [])]
    )

    assert "ca. 10–20 Minuten" in dossier
