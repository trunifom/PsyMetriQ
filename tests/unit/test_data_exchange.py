import csv
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from data.generate_mock_data import generate_mock_data
from schemas.questionnaire_schema import (
    BranchingCondition,
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
    ScoringAlgorithm,
)
from src.exporters.data_exchange import (
    DataExchangeError,
    build_redcap_metadata_records,
    export_fhir_questionnaire,
    export_item_csv,
    export_psymetriq_json,
    export_questionnaire,
    export_redcap_data_dictionary,
    import_fhir_questionnaire,
    import_psymetriq_json,
    import_redcap_data_dictionary,
    select_questionnaire_items,
)


@pytest.fixture
def synthetic_questionnaire(tmp_path: Path) -> QuestionnaireParent:
    generated_paths = generate_mock_data(tmp_path)
    return QuestionnaireParent.model_validate_json(
        generated_paths[0].read_text(encoding="utf-8")
    )


def test_psymetriq_json_export_import_round_trip(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    serialized = export_psymetriq_json([synthetic_questionnaire])

    imported = import_psymetriq_json(serialized)

    assert imported == [synthetic_questionnaire]


def test_fhir_questionnaire_preserves_family_version_items_and_scales(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]

    exported = export_fhir_questionnaire(synthetic_questionnaire, version)
    imported = import_fhir_questionnaire(exported)

    assert imported.instrument_id == synthetic_questionnaire.instrument_id
    assert imported.name_full == synthetic_questionnaire.name_full
    assert imported.versions[0].version_id == version.version_id
    assert imported.versions[0].language == version.language
    assert [item.prompt_text for item in imported.versions[0].items] == [
        item.prompt_text for item in version.items
    ]
    first_item = imported.versions[0].items[0]
    original_item = version.items[0]
    assert imported.versions[0].response_sets[first_item.response_set_ref] == version.response_sets[
        original_item.response_set_ref
    ]


def test_redcap_dictionary_preserves_fields_without_inventing_scores(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    redcap_csv = export_redcap_data_dictionary(synthetic_questionnaire, version)

    imported = import_redcap_data_dictionary(redcap_csv, language=version.language)

    assert imported.is_commercial is None
    assert imported.versions[0].language == version.language
    assert [item.prompt_text for item in imported.versions[0].items] == [
        item.prompt_text for item in version.items
    ]
    original_options = version.response_sets[version.items[0].response_set_ref]
    imported_options = imported.versions[0].response_sets[
        imported.versions[0].items[0].response_set_ref
    ]
    assert [option.label for option in imported_options] == [
        option.label for option in original_options
    ]
    assert all(option.score is None for option in imported_options)


def test_item_csv_uses_standard_quoting_for_multiline_or_comma_text(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    csv_text = export_item_csv(synthetic_questionnaire, version)
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(rows) == len(version.items)
    assert rows[0]["instrument_id"] == synthetic_questionnaire.instrument_id
    assert rows[0]["prompt_text"] == version.items[0].prompt_text
    assert json.loads(rows[0]["response_options"])


def test_xlsx_export_contains_items_responses_scoring_and_sources(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]

    extension, workbook_bytes = export_questionnaire(family, version.version_id, "xlsx")
    workbook = load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=True)

    assert extension == ".xlsx"
    assert workbook.sheetnames == ["Items", "Antwortoptionen", "Scoring", "Quellen"]
    rows = list(workbook["Items"].values)
    headers = list(rows[0])
    first_item = dict(zip(headers, rows[1], strict=True))
    assert first_item["Item ID"] == version.items[0].item_id
    assert first_item["Itemtext"] == version.items[0].prompt_text
    assert list(workbook["Antwortoptionen"].values)[1][2] == next(
        iter(version.response_sets.values())
    )[0].label
    workbook.close()


def test_xlsx_keeps_formula_like_item_text_as_literal_string(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]
    formula_like = version.items[0].model_copy(update={"prompt_text": "=1+1"})
    version = version.model_copy(update={"items": [formula_like, *version.items[1:]]})
    family = family.model_copy(update={"versions": [version]})

    _extension, workbook_bytes = export_questionnaire(family, version.version_id, "xlsx")
    workbook = load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=False)
    item_row = list(workbook["Items"].values)[1]

    assert item_row[9] == "=1+1"
    assert workbook["Items"]["J2"].data_type == "s"
    workbook.close()


def test_required_items_round_trip_through_fhir_and_redcap(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]
    required_item = version.items[0].model_copy(update={"is_required": True})
    version = version.model_copy(update={"items": [required_item, *version.items[1:]]})
    family = family.model_copy(update={"versions": [version]})

    fhir_resource = export_fhir_questionnaire(family, version)
    imported_fhir = import_fhir_questionnaire(fhir_resource)
    redcap_csv = export_redcap_data_dictionary(family, version)
    imported_redcap = import_redcap_data_dictionary(redcap_csv, language=version.language)

    assert fhir_resource["item"][0]["required"] is True
    assert imported_fhir.versions[0].items[0].is_required is True
    assert imported_redcap.versions[0].items[0].is_required is True


def test_requiredness_survives_fhir_and_redcap_round_trips(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    family = synthetic_questionnaire
    version = family.versions[0]
    required_item = version.items[0].model_copy(update={"is_required": True})
    version = version.model_copy(
        update={"items": [required_item, *version.items[1:]]}
    )
    family = family.model_copy(update={"versions": [version]})

    fhir = export_fhir_questionnaire(family, version)
    imported_fhir = import_fhir_questionnaire(fhir)
    redcap = export_redcap_data_dictionary(family, version)
    imported_redcap = import_redcap_data_dictionary(redcap, language=version.language)

    assert fhir["item"][0]["required"] is True
    assert imported_fhir.versions[0].items[0].is_required is True
    assert imported_redcap.versions[0].items[0].is_required is True


def test_psymetriq_json_rejects_duplicate_instrument_ids(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    with pytest.raises(DataExchangeError, match="duplicate instrument_id"):
        import_psymetriq_json(
            json.dumps([synthetic_questionnaire.model_dump(mode="json")] * 2)
        )


def test_redcap_import_requires_expected_dictionary_headers() -> None:
    with pytest.raises(DataExchangeError, match="missing required"):
        import_redcap_data_dictionary("a,b\n1,2\n", language="en")


def test_export_rejects_unknown_version(synthetic_questionnaire: QuestionnaireParent) -> None:
    with pytest.raises(DataExchangeError, match="Unknown questionnaire version"):
        from src.exporters.data_exchange import export_questionnaire

        export_questionnaire(synthetic_questionnaire, "missing", "fhir_json")


def _reverse_scored_family() -> QuestionnaireParent:
    """A synthetic instrument modeled on the real Rosenberg Self-Esteem catalog entry.

    Reverse- and forward-keyed items share the *same* response set, which
    records each option's forward-direction score once (a 0-3 agreement
    scale in two equivalent codings). Reversal must therefore come from
    ``item.is_reverse_scored`` applied on top of that shared score, via the
    standard ``(min + max) - value`` formula -- the score field alone does
    not already encode it. ``rev_01`` uses non-identity (string) codes to
    also exercise the recode path together with reversal; ``direct_01``
    uses identity-coded (numeric) codes to exercise the fast path alone.
    """
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "agree_letters_4": [
                ResponseOption(code="SA", label="strongly agree", score=3),
                ResponseOption(code="A", label="agree", score=2),
                ResponseOption(code="D", label="disagree", score=1),
                ResponseOption(code="SD", label="strongly disagree", score=0),
            ],
            "agree_numeric_4": [
                ResponseOption(code=0, label="never", score=0),
                ResponseOption(code=1, label="always", score=1),
            ],
        },
        items=[
            ItemSchema(
                item_id="rev_01",
                variable_name="rev_01",
                dimension="core",
                prompt_text="Reverse-scored item.",
                response_set_ref="agree_letters_4",
                is_reverse_scored=True,
            ),
            ItemSchema(
                item_id="direct_01",
                variable_name="direct_01",
                dimension="core",
                prompt_text="Directly-scored item.",
                response_set_ref="agree_numeric_4",
            ),
            ItemSchema(
                item_id="slider_01",
                variable_name="slider_01",
                dimension="core",
                prompt_text="How much pain right now?",
                response_mode="numeric",
                numeric_minimum=0,
                numeric_maximum=100,
                redcap_field_type="slider",
                is_scored=False,
            ),
        ],
        scoring_algorithms=[
            ScoringAlgorithm(
                output_variable="core_total",
                method="sum",
                target_items=["rev_01", "direct_01"],
                multiplier=2,
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id="reverse_demo",
        name_full="Reverse Scoring Demonstration Instrument",
        is_commercial=False,
        versions=[version],
    )


def test_redcap_export_recodes_reverse_scored_items_in_the_calc_field() -> None:
    family = _reverse_scored_family()
    version = family.versions[0]

    records = build_redcap_metadata_records(family, version)

    calc_records = [record for record in records if record["field_type"] == "calc"]
    assert len(calc_records) == 1
    calc_expression = calc_records[0]["select_choices_or_calculations"]
    # rev_01 is recoded via its string codes, then reversed over its 0-3 range.
    assert "if([rev_01]='SA',3" in calc_expression
    assert "if([rev_01]='SD',0" in calc_expression
    assert "(3-(" in calc_expression
    # direct_01 is identity-coded and never reversed: used as-is.
    assert "[direct_01]" in calc_expression
    assert "(3-([direct_01]" not in calc_expression
    assert calc_expression.endswith("*2)")
    assert calc_records[0]["field_name"] != "rev_01"
    assert calc_records[0]["field_name"] != "direct_01"


def test_redcap_export_reverses_an_identity_coded_item_on_the_fast_path() -> None:
    """The (min+max)-value reversal must also apply when code == score (fast path)."""
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "agree_numeric_4": [
                ResponseOption(code=0, label="never", score=0),
                ResponseOption(code=1, label="rarely", score=1),
                ResponseOption(code=2, label="often", score=2),
                ResponseOption(code=3, label="always", score=3),
            ]
        },
        items=[
            ItemSchema(
                item_id="rev_02",
                variable_name="rev_02",
                dimension="core",
                prompt_text="Reverse-scored, identity-coded item.",
                response_set_ref="agree_numeric_4",
                is_reverse_scored=True,
            )
        ],
        scoring_algorithms=[
            ScoringAlgorithm(output_variable="total", method="sum", target_items=["rev_02"])
        ],
    )
    family = QuestionnaireParent(
        instrument_id="reverse_fast_path_demo",
        name_full="Reverse Fast-Path Demonstration Instrument",
        is_commercial=False,
        versions=[version],
    )

    records = build_redcap_metadata_records(family, version)

    calc_expression = next(r for r in records if r["field_type"] == "calc")[
        "select_choices_or_calculations"
    ]
    assert calc_expression == "((3-([rev_02])))"


def test_redcap_export_honors_slider_field_type_with_min_max_labels() -> None:
    family = _reverse_scored_family()
    version = family.versions[0]

    records = build_redcap_metadata_records(family, version)

    slider_record = next(record for record in records if record["field_name"] == "slider_01")
    assert slider_record["field_type"] == "slider"
    assert slider_record["select_choices_or_calculations"] == "0, , 100"


def test_redcap_csv_export_includes_calc_and_slider_rows() -> None:
    family = _reverse_scored_family()
    version = family.versions[0]

    csv_text = export_redcap_data_dictionary(family, version)
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    field_types = {row["Variable / Field Name"]: row["Field Type"] for row in rows}
    assert field_types["slider_01"] == "slider"
    calc_rows = [row for row in rows if row["Field Type"] == "calc"]
    assert len(calc_rows) == 1
    assert calc_rows[0]["Variable / Field Name"] not in {"rev_01", "direct_01", "slider_01"}


def _write_redcap_csv(rows: list[dict[str, str]]) -> str:
    """Build a real, correctly quoted REDCap Data Dictionary CSV for a test fixture."""
    headers = [
        "Variable / Field Name",
        "Form Name",
        "Section Header",
        "Field Type",
        "Field Label",
        "Choices, Calculations, OR Slider Labels",
        "Field Note",
        "Text Validation Type OR Show Slider Number",
        "Text Validation Min",
        "Text Validation Max",
        "Required Field?",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in headers})
    return output.getvalue()


def test_redcap_import_recognizes_yesno_truefalse_and_slider_fields() -> None:
    csv_text = _write_redcap_csv(
        [
            {
                "Variable / Field Name": "q_yn",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "yesno",
                "Field Label": "Do you smoke?",
            },
            {
                "Variable / Field Name": "q_tf",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "truefalse",
                "Field Label": "I feel anxious.",
            },
            {
                "Variable / Field Name": "q_slider",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "slider",
                "Field Label": "Rate your mood",
                "Choices, Calculations, OR Slider Labels": "0, , 100",
            },
        ]
    )

    imported = import_redcap_data_dictionary(csv_text, language="en")

    items_by_id = {item.item_id: item for item in imported.versions[0].items}
    yesno_item = items_by_id["q_yn"]
    assert yesno_item.response_mode == "categorical"
    yesno_options = imported.versions[0].response_sets[yesno_item.response_set_ref]
    assert {option.label for option in yesno_options} == {"Yes", "No"}

    truefalse_item = items_by_id["q_tf"]
    truefalse_options = imported.versions[0].response_sets[truefalse_item.response_set_ref]
    assert {option.label for option in truefalse_options} == {"True", "False"}

    slider_item = items_by_id["q_slider"]
    assert slider_item.response_mode == "numeric"
    assert slider_item.redcap_field_type == "slider"


def test_redcap_import_notes_skipped_non_respondent_field_types() -> None:
    csv_text = _write_redcap_csv(
        [
            {
                "Variable / Field Name": "q_text",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "text",
                "Field Label": "A normal question",
            },
            {
                "Variable / Field Name": "q_total",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "calc",
                "Field Label": "Total score",
                "Choices, Calculations, OR Slider Labels": "[q_text]",
            },
            {
                "Variable / Field Name": "q_intro",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "descriptive",
                "Field Label": "Please read the instructions carefully",
            },
        ]
    )

    imported = import_redcap_data_dictionary(csv_text, language="en")

    assert len(imported.versions[0].items) == 1
    assert imported.metadata.notes is not None
    assert "q_total (calc)" in imported.metadata.notes
    assert "q_intro (descriptive)" in imported.metadata.notes


def test_item_subset_keeps_valid_scoring_only_when_all_targets_are_selected(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    selected = select_questionnaire_items(
        synthetic_questionnaire,
        version.version_id,
        [version.items[0].item_id],
    )

    assert len(selected.versions[0].items) == 1
    assert selected.versions[0].response_sets.keys() == {
        version.items[0].response_set_ref
    }
    assert selected.versions[0].scoring_algorithms == []


def test_item_subset_rejects_unknown_saved_references(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    with pytest.raises(DataExchangeError, match="unknown item IDs"):
        select_questionnaire_items(
            synthetic_questionnaire,
            synthetic_questionnaire.versions[0].version_id,
            ["missing_item"],
        )


def test_study_adaptation_changes_only_derived_export_and_drops_affected_scores(
    synthetic_questionnaire: QuestionnaireParent,
) -> None:
    version = synthetic_questionnaire.versions[0]
    original_prompt = version.items[0].prompt_text
    adapted = select_questionnaire_items(
        synthetic_questionnaire,
        version.version_id,
        [],
        {version.items[0].item_id: ("Study-specific wording", "Clarified the study timeframe")},
    )

    assert synthetic_questionnaire.versions[0].items[0].prompt_text == original_prompt
    assert adapted.versions[0].items[0].prompt_text == "Study-specific wording"
    assert "not been psychometrically validated" in adapted.versions[0].items[0].metadata.notes
    assert adapted.versions[0].scoring_algorithms == []


def _branching_family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "yesno": [
                ResponseOption(code=1, label="Yes", score=None),
                ResponseOption(code=0, label="No", score=None),
            ]
        },
        items=[
            ItemSchema(
                item_id="gate_01",
                variable_name="gate_01",
                dimension="core",
                prompt_text="Have you ever smoked?",
                response_set_ref="yesno",
            ),
            ItemSchema(
                item_id="follow_01",
                variable_name="follow_01",
                dimension="core",
                prompt_text="How many cigarettes per day?",
                response_mode="numeric",
                is_scored=False,
                show_if=[BranchingCondition(source_item_id="gate_01", value="1")],
                matrix_group_name="smoking_matrix",
                matrix_ranking=True,
            ),
        ],
    )
    return QuestionnaireParent(
        instrument_id="branching_demo",
        name_full="Branching Logic Demonstration Instrument",
        is_commercial=False,
        versions=[version],
    )


def test_redcap_export_renders_branching_logic_and_matrix_fields() -> None:
    family = _branching_family()
    version = family.versions[0]

    records = build_redcap_metadata_records(family, version)

    follow_up = next(record for record in records if record["field_name"] == "follow_01")
    assert follow_up["branching_logic"] == "[gate_01]='1'"
    assert follow_up["matrix_group_name"] == "smoking_matrix"
    assert follow_up["matrix_ranking"] == "y"
    gate = next(record for record in records if record["field_name"] == "gate_01")
    assert gate["branching_logic"] == ""


def test_redcap_export_renders_not_equals_and_multiple_conditions() -> None:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "s": [
                ResponseOption(code=1, label="A", score=None),
                ResponseOption(code=2, label="B", score=None),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Q1",
                response_set_ref="s",
            ),
            ItemSchema(
                item_id="q2",
                variable_name="q2",
                dimension="core",
                prompt_text="Q2",
                response_set_ref="s",
            ),
            ItemSchema(
                item_id="q3",
                variable_name="q3",
                dimension="core",
                prompt_text="Q3",
                response_set_ref="s",
                show_if=[
                    BranchingCondition(source_item_id="q1", operator="not_equals", value="2"),
                    BranchingCondition(source_item_id="q2", operator="equals", value="1"),
                ],
            ),
        ],
    )
    family = QuestionnaireParent(
        instrument_id="demo", name_full="Demo", is_commercial=False, versions=[version]
    )

    records = build_redcap_metadata_records(family, version)

    q3 = next(record for record in records if record["field_name"] == "q3")
    assert q3["branching_logic"] == "[q1]<>'2' and [q2]='1'"


def _redcap_csv_with_headers(headers: list[str], rows: list[dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in headers})
    return output.getvalue()


def test_redcap_import_parses_a_simple_branching_logic_chain() -> None:
    headers = [
        "Variable / Field Name", "Form Name", "Section Header", "Field Type", "Field Label",
        "Branching Logic (Show field only if...)",
    ]
    csv_text = _redcap_csv_with_headers(
        headers,
        [
            {
                "Variable / Field Name": "gate_01",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "yesno",
                "Field Label": "Have you ever smoked?",
            },
            {
                "Variable / Field Name": "follow_01",
                "Form Name": "demo",
                "Section Header": "core",
                "Field Type": "text",
                "Field Label": "How many cigarettes per day?",
                "Branching Logic (Show field only if...)": "[gate_01]='1'",
            },
        ],
    )

    imported = import_redcap_data_dictionary(csv_text, language="en")

    items_by_id = {item.item_id: item for item in imported.versions[0].items}
    follow_up = items_by_id["follow_01"]
    assert len(follow_up.show_if) == 1
    assert follow_up.show_if[0].operator == "equals"
    assert follow_up.show_if[0].value == "1"
    assert follow_up.show_if[0].source_item_id == items_by_id["gate_01"].item_id


def test_redcap_import_preserves_unparseable_branching_logic_as_a_note() -> None:
    headers = [
        "Variable / Field Name", "Form Name", "Section Header", "Field Type", "Field Label",
        "Branching Logic (Show field only if...)",
    ]
    csv_text = _redcap_csv_with_headers(
        headers,
        [
            {
                "Variable / Field Name": "q1", "Form Name": "demo", "Section Header": "core",
                "Field Type": "text", "Field Label": "Q1",
            },
            {
                "Variable / Field Name": "q2", "Form Name": "demo", "Section Header": "core",
                "Field Type": "text", "Field Label": "Q2",
                "Branching Logic (Show field only if...)": "([q1]='1' or [q1]='2')",
            },
        ],
    )

    imported = import_redcap_data_dictionary(csv_text, language="en")

    items_by_id = {item.item_id: item for item in imported.versions[0].items}
    q2 = items_by_id["q2"]
    assert q2.show_if == []
    assert "not structurally parsed" in (q2.metadata.notes or "")
    assert "[q1]='1' or [q1]='2'" in q2.metadata.notes


def test_redcap_import_reads_matrix_group_and_ranking_columns() -> None:
    headers = [
        "Variable / Field Name", "Form Name", "Section Header", "Field Type", "Field Label",
        "Matrix Group Name", "Matrix Ranking?",
    ]
    csv_text = _redcap_csv_with_headers(
        headers,
        [
            {
                "Variable / Field Name": "q1", "Form Name": "demo", "Section Header": "core",
                "Field Type": "text", "Field Label": "Q1",
                "Matrix Group Name": "grid_a", "Matrix Ranking?": "y",
            }
        ],
    )

    imported = import_redcap_data_dictionary(csv_text, language="en")

    item = imported.versions[0].items[0]
    assert item.matrix_group_name == "grid_a"
    assert item.matrix_ranking is True
