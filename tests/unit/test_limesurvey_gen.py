from schemas.questionnaire_schema import (
    BranchingCondition,
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
    ScoringAlgorithm,
)
from src.exporters.limesurvey_gen import (
    LimeSurveyExportError,
    LimeSurveyImportError,
    build_limesurvey_rows,
    export_limesurvey_tsv,
    import_limesurvey_tsv,
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
                ResponseOption(code=3, label="Always", score=3),
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
                prompt_text="How often does this affect you?",
                response_set_ref="freq_4",
                show_if=[BranchingCondition(source_item_id="q1", operator="not_equals", value="0")],
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
        scoring_algorithms=[
            ScoringAlgorithm(output_variable="total", method="sum", target_items=["q1", "q2"])
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo", name_full="Demo Instrument", is_commercial=False, versions=[version]
    )


def test_build_limesurvey_rows_includes_required_survey_and_group_rows() -> None:
    family = _demo_family()

    rows = build_limesurvey_rows(family, family.versions[0])

    classes = [row["class"] for row in rows]
    assert classes[0] == "S"
    assert rows[0]["name"] == "language"
    assert rows[0]["text"] == "en"
    assert "SL" in classes
    assert "G" in classes


def test_build_limesurvey_rows_maps_question_types_and_relevance() -> None:
    family = _demo_family()

    rows = build_limesurvey_rows(family, family.versions[0])

    q1 = next(row for row in rows if row.get("name") == "q1" and row["class"] == "Q")
    assert q1["type/scale"] == "L"
    assert q1["relevance"] == "1"
    assert q1["mandatory"] == "Y"

    q2 = next(row for row in rows if row.get("name") == "q2" and row["class"] == "Q")
    assert q2["relevance"] == '(q1 != "0")'

    q3 = next(row for row in rows if row.get("name") == "q3" and row["class"] == "Q")
    assert q3["type/scale"] == "S"


def test_build_limesurvey_rows_exports_answer_options_with_assessment_value() -> None:
    family = _demo_family()

    rows = build_limesurvey_rows(family, family.versions[0])

    answer_rows = [row for row in rows if row["class"] == "A"]
    assert len(answer_rows) == 8  # 4 options x 2 categorical items
    first = answer_rows[0]
    assert first["name"] == "0"
    assert first["text"] == "Never"
    assert first["assessment_value"] == "0"


def test_build_limesurvey_rows_rejects_a_version_with_no_items() -> None:
    version = QuestionnaireVersion(version_id="v1", language="en", item_text_included=False)
    family = QuestionnaireParent(
        instrument_id="empty", name_full="Empty", is_commercial=False, versions=[version]
    )

    try:
        build_limesurvey_rows(family, version)
    except LimeSurveyExportError:
        pass
    else:
        raise AssertionError("expected LimeSurveyExportError")


def test_export_limesurvey_tsv_produces_a_tab_separated_header() -> None:
    family = _demo_family()

    tsv = export_limesurvey_tsv(family, family.versions[0])

    header = tsv.splitlines()[0]
    assert header.split("\t")[:5] == ["id", "related_id", "class", "type/scale", "name"]


def test_import_limesurvey_tsv_round_trips_items_and_response_options() -> None:
    family = _demo_family()
    tsv = export_limesurvey_tsv(family, family.versions[0])

    imported = import_limesurvey_tsv(tsv, default_language="en")

    assert imported.name_full.startswith("Demo Instrument")
    assert imported.versions[0].language == "en"
    assert len(imported.versions[0].items) == 3
    q1 = next(item for item in imported.versions[0].items if item.variable_name == "q1")
    options = imported.versions[0].response_sets[q1.response_set_ref]
    assert [option.label for option in options] == ["Never", "Sometimes", "Often", "Always"]
    assert [option.score for option in options] == [0, 1, 2, 3]


def test_import_limesurvey_tsv_parses_a_simple_relevance_chain() -> None:
    family = _demo_family()
    tsv = export_limesurvey_tsv(family, family.versions[0])

    imported = import_limesurvey_tsv(tsv, default_language="en")

    items_by_variable = {item.variable_name: item for item in imported.versions[0].items}
    q2 = items_by_variable["q2"]
    assert len(q2.show_if) == 1
    assert q2.show_if[0].operator == "not_equals"
    assert q2.show_if[0].value == "0"
    assert q2.show_if[0].source_item_id == items_by_variable["q1"].item_id


def test_import_limesurvey_tsv_preserves_unparseable_relevance_as_a_note() -> None:
    tsv = (
        "id\trelated_id\tclass\ttype/scale\tname\trelevance\ttext\thelp\tlanguage\t"
        "validation\tmandatory\tother\tdefault\tassessment_value\n"
        "\t\tS\t\tlanguage\t\ten\t\t\t\t\t\t\t\n"
        '\t\tQ\tL\tq1\t(q0 == "1" or q0 == "2")\tQ1\t\ten\t\tN\t\t\t\n'
        "\t\tA\t0\t1\t\tYes\t\ten\t\t\t\t\t1\n"
        "\t\tA\t0\t0\t\tNo\t\ten\t\t\t\t\t0\n"
    )

    imported = import_limesurvey_tsv(tsv, default_language="en")

    q1 = imported.versions[0].items[0]
    assert q1.show_if == []
    assert "not structurally parsed" in (q1.metadata.notes or "")
    assert 'q0 == "1" or q0 == "2"' in q1.metadata.notes


def test_import_limesurvey_tsv_notes_skipped_question_types() -> None:
    tsv = (
        "class\tname\ttext\ttype/scale\tlanguage\n"
        "S\tlanguage\t\t\ten\n"
        "Q\tq1\tA text question\tS\ten\n"
        "Q\tq2\tA ranking question\tR\ten\n"
    )

    imported = import_limesurvey_tsv(tsv, default_language="en")

    assert len(imported.versions[0].items) == 1
    assert "q2 (type R)" in (imported.metadata.notes or "")


def test_import_limesurvey_tsv_downgrades_a_categorical_question_with_no_answers() -> None:
    tsv = (
        "class\tname\ttext\ttype/scale\tlanguage\n"
        "S\tlanguage\t\t\ten\n"
        "Q\tq1\tA radio question with no options\tL\ten\n"
    )

    imported = import_limesurvey_tsv(tsv, default_language="en")

    item = imported.versions[0].items[0]
    assert item.response_mode == "text"
    assert item.response_set_ref is None
    assert "Imported as free text" in (item.metadata.notes or "")


def test_import_limesurvey_tsv_rejects_content_without_required_headers() -> None:
    try:
        import_limesurvey_tsv("a\tb\n1\t2\n")
    except LimeSurveyImportError:
        pass
    else:
        raise AssertionError("expected LimeSurveyImportError")


def test_import_limesurvey_tsv_rejects_content_with_no_questions() -> None:
    tsv = "class\tname\ttext\n" "S\tlanguage\ten\n"

    try:
        import_limesurvey_tsv(tsv)
    except LimeSurveyImportError:
        pass
    else:
        raise AssertionError("expected LimeSurveyImportError")


def test_import_limesurvey_tsv_disambiguates_names_sharing_a_long_common_prefix() -> None:
    """Regression test: a numeric disambiguation suffix must not itself be
    truncated away by the same length cap that created the collision."""
    long_prefix = "a" * 25  # longer than the 20-character variable_name/40-character item_id caps
    tsv = (
        "class\tname\ttext\ttype/scale\tlanguage\n"
        "S\tlanguage\t\t\ten\n"
        f"Q\t{long_prefix}_one\tQ1\tS\ten\n"
        f"Q\t{long_prefix}_two\tQ2\tS\ten\n"
    )

    imported = import_limesurvey_tsv(tsv, default_language="en")

    variable_names = [item.variable_name for item in imported.versions[0].items]
    item_ids = [item.item_id for item in imported.versions[0].items]
    assert len(set(variable_names)) == 2
    assert len(set(item_ids)) == 2
