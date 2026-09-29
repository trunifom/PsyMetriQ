from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)
from src.core.battery_time_estimator import (
    estimate_battery_time,
    estimate_version_time,
    parse_administration_time,
)


def _family_with_items(*, administration_time: str | None = None) -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        administration_time=administration_time,
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
                response_mode="text",
                is_scored=False,
            ),
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo", name_full="Demo Instrument", is_commercial=False, versions=[version]
    )


def _reference_family(
    *, administration_time: str | None = None, source_reported_item_count: int | None = None
) -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        item_text_included=False,
        administration_time=administration_time,
        source_reported_item_count=source_reported_item_count,
    )
    return QuestionnaireParent(
        instrument_id="ref",
        name_full="Reference Instrument",
        is_commercial=None,
        versions=[version],
    )


def test_parse_administration_time_handles_a_range() -> None:
    assert parse_administration_time("ca. 5-10 Minuten") == (5.0, 10.0)


def test_parse_administration_time_handles_a_single_value() -> None:
    assert parse_administration_time("ca. 5 Minuten") == (5.0, 5.0)


def test_parse_administration_time_handles_an_upper_bound_only() -> None:
    assert parse_administration_time("unter 2 Minuten") == (0.0, 2.0)


def test_parse_administration_time_handles_a_range_with_extra_text() -> None:
    assert parse_administration_time("formabhängig; ca. 10-20 Minuten") == (10.0, 20.0)


def test_parse_administration_time_returns_none_when_unparseable() -> None:
    assert parse_administration_time("formabhängig; Quelle konsultieren") is None


def test_parse_administration_time_returns_none_for_empty_text() -> None:
    assert parse_administration_time(None) is None
    assert parse_administration_time("") is None


def test_estimate_version_time_prefers_a_parseable_source_reported_time() -> None:
    family = _family_with_items(administration_time="ca. 5-10 Minuten")

    estimate = estimate_version_time(family, family.versions[0])

    assert estimate.source == "source_reported"
    assert estimate.minimum_minutes == 5.0
    assert estimate.maximum_minutes == 10.0


def test_estimate_version_time_falls_back_to_item_heuristic_when_unparseable() -> None:
    family = _family_with_items(administration_time="formabhängig; Quelle konsultieren")

    estimate = estimate_version_time(family, family.versions[0])

    assert estimate.source == "heuristic_item_count"
    assert estimate.minimum_minutes is not None
    assert estimate.minimum_minutes < estimate.maximum_minutes


def test_estimate_version_time_heuristic_narrows_to_a_selected_item_subset() -> None:
    family = _family_with_items()

    full = estimate_version_time(family, family.versions[0])
    narrowed = estimate_version_time(family, family.versions[0], item_ids=["q1"])

    assert narrowed.minimum_minutes < full.minimum_minutes


def test_estimate_version_time_falls_back_to_source_reported_item_count() -> None:
    family = _reference_family(source_reported_item_count=20)

    estimate = estimate_version_time(family, family.versions[0])

    assert estimate.source == "heuristic_item_count"
    assert estimate.minimum_minutes is not None
    assert estimate.minimum_minutes > 0


def test_estimate_version_time_is_unknown_without_any_time_or_item_count() -> None:
    family = _reference_family()

    estimate = estimate_version_time(family, family.versions[0])

    assert estimate.source == "unknown"
    assert estimate.minimum_minutes is None
    assert estimate.maximum_minutes is None


def test_estimate_battery_time_sums_known_entries_and_flags_unknown_ones() -> None:
    known = _family_with_items(administration_time="ca. 5-10 Minuten")
    unknown = _reference_family()

    battery = estimate_battery_time(
        [
            (known, known.versions[0], []),
            (unknown, unknown.versions[0], []),
        ]
    )

    assert battery.minimum_minutes == 5.0
    assert battery.maximum_minutes == 10.0
    assert battery.has_unknown_entries is True


def test_estimate_battery_time_returns_none_totals_when_nothing_is_known() -> None:
    unknown = _reference_family()

    battery = estimate_battery_time([(unknown, unknown.versions[0], [])])

    assert battery.minimum_minutes is None
    assert battery.maximum_minutes is None
