from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
    ScoringAlgorithm,
)
from src.exporters.r_syntax_gen import export_r_syntax


def _family_with(
    *,
    reverse_scored: bool,
    response_set_name: str = "agree_letters_4",
    codes: list[tuple[str | int, float]] | None = None,
) -> QuestionnaireParent:
    codes = codes or [("SA", 3), ("A", 2), ("D", 1), ("SD", 0)]
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            response_set_name: [
                ResponseOption(code=code, label=str(code), score=score) for code, score in codes
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text='A demo item with a "quote" and a\nnewline.',
                response_set_ref=response_set_name,
                is_reverse_scored=reverse_scored,
            )
        ],
        scoring_algorithms=[
            ScoringAlgorithm(output_variable="demo total!", method="sum", target_items=["q1"])
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo",
        name_full="Demo Instrument",
        is_commercial=False,
        versions=[version],
    )


def test_export_r_syntax_escapes_quotes_and_newlines_in_labels() -> None:
    family = _family_with(reverse_scored=False)

    script = export_r_syntax(family, family.versions[0])

    assert 'attr(df$q1, "label") <- "A demo item with a \\"quote\\" and a\\nnewline."' in script


def test_export_r_syntax_uses_the_raw_column_for_identity_coded_non_reversed_items() -> None:
    family = _family_with(
        reverse_scored=False,
        response_set_name="agree_numeric_4",
        codes=[(0, 0), (1, 1), (2, 2), (3, 3)],
    )

    script = export_r_syntax(family, family.versions[0])

    assert "df$demo_total <- rowSums(cbind(df$q1), na.rm = TRUE)" in script
    assert ".recode_q1" not in script


def test_export_r_syntax_reverses_an_identity_coded_item() -> None:
    family = _family_with(
        reverse_scored=True,
        response_set_name="agree_numeric_4",
        codes=[(0, 0), (1, 1), (2, 2), (3, 3)],
    )

    script = export_r_syntax(family, family.versions[0])

    assert "rowSums(cbind((3 - (df$q1))), na.rm = TRUE)" in script


def test_export_r_syntax_recodes_and_reverses_non_identity_coded_items() -> None:
    family = _family_with(reverse_scored=True)

    script = export_r_syntax(family, family.versions[0])

    assert ".recode_q1 <- c(`SA` = 3, `A` = 2, `D` = 1, `SD` = 0)" in script
    assert "(3 - (unname(.recode_q1[as.character(df$q1)])))" in script


def test_export_r_syntax_applies_the_multiplier() -> None:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "s": [
                ResponseOption(code=0, label="a", score=0),
                ResponseOption(code=1, label="b", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Q1",
                response_set_ref="s",
            )
        ],
        scoring_algorithms=[
            ScoringAlgorithm(
                output_variable="total", method="sum", target_items=["q1"], multiplier=2
            )
        ],
    )
    family = QuestionnaireParent(
        instrument_id="demo", name_full="Demo", is_commercial=False, versions=[version]
    )

    script = export_r_syntax(family, version)

    assert "df$total <- (rowSums(cbind(df$q1), na.rm = TRUE)) * 2" in script


def test_export_r_syntax_uses_rowmeans_for_the_mean_method() -> None:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "s": [
                ResponseOption(code=0, label="a", score=0),
                ResponseOption(code=1, label="b", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Q1",
                response_set_ref="s",
            )
        ],
        scoring_algorithms=[
            ScoringAlgorithm(output_variable="mean_score", method="mean", target_items=["q1"])
        ],
    )
    family = QuestionnaireParent(
        instrument_id="demo", name_full="Demo", is_commercial=False, versions=[version]
    )

    script = export_r_syntax(family, version)

    assert "df$mean_score <- rowMeans(cbind(df$q1), na.rm = TRUE)" in script


def test_export_r_syntax_sanitizes_an_unsafe_output_variable_name() -> None:
    family = _family_with(reverse_scored=False)

    script = export_r_syntax(family, family.versions[0])

    # "demo total!" is not a valid R identifier as-is.
    assert "df$demo_total <-" in script


def test_export_r_syntax_notes_when_no_scoring_algorithms_are_documented() -> None:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "s": [
                ResponseOption(code=0, label="a", score=0),
                ResponseOption(code=1, label="b", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Q1",
                response_set_ref="s",
            )
        ],
    )
    family = QuestionnaireParent(
        instrument_id="demo", name_full="Demo", is_commercial=False, versions=[version]
    )

    script = export_r_syntax(family, version)

    assert "No scoring algorithms are documented for this version." in script
