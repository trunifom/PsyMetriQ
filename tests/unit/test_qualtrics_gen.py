from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)
from src.exporters.qualtrics_gen import (
    QualtricsExportError,
    QualtricsImportError,
    build_qualtrics_survey,
    export_qualtrics_qsf,
    import_qualtrics_qsf,
)


def _demo_family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "freq_4": [
                ResponseOption(code=0, label="Never", score=0),
                ResponseOption(code=1, label="Sometimes", score=1),
                ResponseOption(code=2, label="Often", score=2),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Do you feel anxious?",
                response_set_ref="freq_4",
                is_required=True,
            ),
            ItemSchema(
                item_id="q2",
                variable_name="q2",
                dimension="core",
                prompt_text="How many hours do you sleep?",
                response_mode="numeric",
                is_scored=False,
            ),
            ItemSchema(
                item_id="q3",
                variable_name="q3",
                dimension="notes",
                prompt_text="Anything else to add?",
                response_mode="text",
                is_scored=False,
            ),
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo", name_full="Demo Instrument", is_commercial=False, versions=[version]
    )


def test_build_qualtrics_survey_produces_sq_and_bl_elements() -> None:
    family = _demo_family()

    survey = build_qualtrics_survey(family, family.versions[0])

    elements = [el["Element"] for el in survey["SurveyElements"]]
    assert elements.count("SQ") == 3
    assert "BL" in elements
    assert "FL" in elements
    assert survey["SurveyEntry"]["SurveyLanguage"] == "en"


def test_build_qualtrics_survey_maps_question_types_and_choices() -> None:
    family = _demo_family()

    survey = build_qualtrics_survey(family, family.versions[0])

    q1 = next(
        el
        for el in survey["SurveyElements"]
        if el.get("Element") == "SQ" and el["PrimaryAttribute"] == "QID1"
    )
    assert q1["Payload"]["QuestionType"] == "MC"
    assert q1["Payload"]["Selector"] == "SAVR"
    assert q1["Payload"]["Choices"]["1"]["Display"] == "Never"
    assert q1["Payload"]["RecodeValues"]["1"] == "0"
    assert q1["Payload"]["Validation"]["Settings"]["ForceResponse"] == "ON"

    q2 = next(
        el
        for el in survey["SurveyElements"]
        if el.get("Element") == "SQ" and el["PrimaryAttribute"] == "QID2"
    )
    assert q2["Payload"]["QuestionType"] == "TE"
    assert q2["Payload"]["Validation"]["Settings"]["ContentType"] == "ValidNumber"

    q3 = next(
        el
        for el in survey["SurveyElements"]
        if el.get("Element") == "SQ" and el["PrimaryAttribute"] == "QID3"
    )
    assert q3["Payload"]["QuestionType"] == "TE"
    assert "ContentType" not in q3["Payload"]["Validation"]["Settings"]


def test_build_qualtrics_survey_rejects_a_version_with_no_items() -> None:
    version = QuestionnaireVersion(version_id="v1", language="en", item_text_included=False)
    family = QuestionnaireParent(
        instrument_id="empty", name_full="Empty", is_commercial=False, versions=[version]
    )

    try:
        build_qualtrics_survey(family, version)
    except QualtricsExportError:
        pass
    else:
        raise AssertionError("expected QualtricsExportError")


def test_export_qualtrics_qsf_produces_valid_json() -> None:
    family = _demo_family()

    qsf = export_qualtrics_qsf(family, family.versions[0])

    assert '"SurveyElements"' in qsf
    assert qsf.endswith("\n")


def test_import_qualtrics_qsf_round_trips_items_and_response_options() -> None:
    family = _demo_family()
    qsf = export_qualtrics_qsf(family, family.versions[0])

    imported = import_qualtrics_qsf(qsf, default_language="en")

    assert imported.name_full.startswith("Demo Instrument")
    assert imported.versions[0].language == "en"
    assert len(imported.versions[0].items) == 3
    q1 = next(
        item
        for item in imported.versions[0].items
        if item.dimension == "core" and item.response_mode == "categorical"
    )
    options = imported.versions[0].response_sets[q1.response_set_ref]
    assert [option.label for option in options] == ["Never", "Sometimes", "Often"]
    assert [option.code for option in options] == ["0", "1", "2"]
    numeric_item = next(
        item for item in imported.versions[0].items if item.response_mode == "numeric"
    )
    assert numeric_item.prompt_text == "How many hours do you sleep?"
    text_item = next(item for item in imported.versions[0].items if item.dimension == "notes")
    assert text_item.response_mode == "text"


def test_import_qualtrics_qsf_notes_skipped_question_types() -> None:
    document = {
        "SurveyEntry": {"SurveyName": "Skip Test", "SurveyLanguage": "en"},
        "SurveyElements": [
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID1",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "A text question",
                    "DataExportTag": "q1",
                    "QuestionType": "TE",
                    "Selector": "SL",
                },
            },
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID2",
                "Payload": {
                    "QuestionID": "QID2",
                    "QuestionText": "A matrix question",
                    "DataExportTag": "q2",
                    "QuestionType": "Matrix",
                    "Selector": "Likert",
                },
            },
        ],
    }
    import json

    imported = import_qualtrics_qsf(json.dumps(document), default_language="en")

    assert len(imported.versions[0].items) == 1
    assert "QID2 (type Matrix)" in (imported.metadata.notes or "")


def test_import_qualtrics_qsf_downgrades_a_categorical_question_with_no_choices() -> None:
    document = {
        "SurveyEntry": {"SurveyName": "No Choices", "SurveyLanguage": "en"},
        "SurveyElements": [
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID1",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "A radio question with no options",
                    "DataExportTag": "q1",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                },
            }
        ],
    }
    import json

    imported = import_qualtrics_qsf(json.dumps(document), default_language="en")

    item = imported.versions[0].items[0]
    assert item.response_mode == "text"
    assert item.response_set_ref is None
    assert "Imported as free text" in (item.metadata.notes or "")


def test_import_qualtrics_qsf_rejects_content_without_survey_elements() -> None:
    try:
        import_qualtrics_qsf('{"foo": "bar"}')
    except QualtricsImportError:
        pass
    else:
        raise AssertionError("expected QualtricsImportError")


def test_import_qualtrics_qsf_rejects_malformed_json() -> None:
    try:
        import_qualtrics_qsf("not json")
    except QualtricsImportError:
        pass
    else:
        raise AssertionError("expected QualtricsImportError")


def test_import_qualtrics_qsf_rejects_content_with_no_supported_questions() -> None:
    document = {
        "SurveyEntry": {"SurveyName": "Empty", "SurveyLanguage": "en"},
        "SurveyElements": [
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID1",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "A slider question",
                    "DataExportTag": "q1",
                    "QuestionType": "Slider",
                    "Selector": "HSLIDER",
                },
            }
        ],
    }
    import json

    try:
        import_qualtrics_qsf(json.dumps(document))
    except QualtricsImportError:
        pass
    else:
        raise AssertionError("expected QualtricsImportError")


def test_import_qualtrics_qsf_disambiguates_export_tags_sharing_a_long_common_prefix() -> None:
    """Regression test mirroring the LimeSurvey/Unipark/REDCap fix: a numeric
    disambiguation suffix must not itself be truncated away by the same
    26-character variable_name length cap that created the collision."""
    long_prefix = "a" * 25
    document = {
        "SurveyEntry": {"SurveyName": "Collision Test", "SurveyLanguage": "en"},
        "SurveyElements": [
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID1",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "Q1",
                    "DataExportTag": f"{long_prefix}_one",
                    "QuestionType": "TE",
                    "Selector": "SL",
                },
            },
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID2",
                "Payload": {
                    "QuestionID": "QID2",
                    "QuestionText": "Q2",
                    "DataExportTag": f"{long_prefix}_two",
                    "QuestionType": "TE",
                    "Selector": "SL",
                },
            },
        ],
    }
    import json

    imported = import_qualtrics_qsf(json.dumps(document), default_language="en")

    variable_names = [item.variable_name for item in imported.versions[0].items]
    assert len(set(variable_names)) == 2
