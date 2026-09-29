from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)
from src.exporters.unipark_gen import (
    UniparkExportError,
    UniparkImportError,
    export_unipark_text,
    import_unipark_text,
)


def _demo_family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "freq_4": [
                ResponseOption(code=0, label="Never", score=0),
                ResponseOption(code=1, label="Sometimes", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Do you feel anxious?",
                response_set_ref="freq_4",
            ),
            ItemSchema(
                item_id="q2",
                variable_name="q2",
                dimension="core",
                prompt_text="Please state your area of employment.",
                response_mode="text",
                is_scored=False,
            ),
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo", name_full="Demo Instrument", is_commercial=False, versions=[version]
    )


def test_export_unipark_text_renders_question_and_coded_answer_lines() -> None:
    family = _demo_family()

    text = export_unipark_text(family, family.versions[0])

    blocks = text.strip("\n").split("\n\n")
    assert blocks[0] == "Do you feel anxious?\n0;Never\n1;Sometimes"
    assert blocks[1] == "Please state your area of employment."


def test_export_unipark_text_rejects_a_version_with_no_items() -> None:
    version = QuestionnaireVersion(version_id="v1", language="en", item_text_included=False)
    family = QuestionnaireParent(
        instrument_id="empty", name_full="Empty", is_commercial=False, versions=[version]
    )

    try:
        export_unipark_text(family, version)
    except UniparkExportError:
        pass
    else:
        raise AssertionError("expected UniparkExportError")


def test_import_unipark_text_round_trips_categorical_and_text_items() -> None:
    family = _demo_family()
    text = export_unipark_text(family, family.versions[0])

    imported = import_unipark_text(text, language="en")

    assert len(imported.versions[0].items) == 2
    q1 = imported.versions[0].items[0]
    assert q1.response_mode == "categorical"
    options = imported.versions[0].response_sets[q1.response_set_ref]
    assert [(option.code, option.label) for option in options] == [(0, "Never"), (1, "Sometimes")]
    q2 = imported.versions[0].items[1]
    assert q2.response_mode == "text"
    assert q2.response_set_ref is None


def test_import_unipark_text_auto_numbers_answers_without_an_explicit_code() -> None:
    text = "How satisfied are you?\nVery satisfied\nSomewhat satisfied\nNot satisfied\n"

    imported = import_unipark_text(text, language="en")

    options = imported.versions[0].response_sets[imported.versions[0].items[0].response_set_ref]
    assert [option.code for option in options] == [1, 2, 3]
    assert [option.label for option in options] == [
        "Very satisfied",
        "Somewhat satisfied",
        "Not satisfied",
    ]


def test_import_unipark_text_handles_a_semicolon_in_a_non_numeric_answer_gracefully() -> None:
    # A line with a semicolon whose left side isn't a plain integer is treated as
    # one plain answer label (e.g. a label that itself happens to contain ";"),
    # not misparsed as a code.
    text = "Which tools do you use?\n1;Software\nOther; please specify\n"

    imported = import_unipark_text(text, language="en")

    options = imported.versions[0].response_sets[imported.versions[0].items[0].response_set_ref]
    assert options[0].code == 1
    assert options[0].label == "Software"
    assert options[1].label == "Other; please specify"


def test_import_unipark_text_disambiguates_prompts_sharing_a_long_common_prefix() -> None:
    """Regression test: two prompts sharing their first ~40 characters must not
    collide after item_id/variable_name truncation once a numeric suffix is
    appended to break the tie -- appending the suffix must not itself be
    truncated away by re-applying the same length cap."""
    text = (
        "During the past two weeks, how often have you felt low in mood?\n"
        "0;Not at all\n1;A little\n\n"
        "During the past two weeks, how often have you had less interest in hobbies?\n"
        "0;Not at all\n1;A little\n"
    )

    imported = import_unipark_text(text, language="en")

    item_ids = [item.item_id for item in imported.versions[0].items]
    variable_names = [item.variable_name for item in imported.versions[0].items]
    assert len(set(item_ids)) == 2
    assert len(set(variable_names)) == 2


def test_import_unipark_text_rejects_empty_content() -> None:
    try:
        import_unipark_text("   \n\n  ")
    except UniparkImportError:
        pass
    else:
        raise AssertionError("expected UniparkImportError")
