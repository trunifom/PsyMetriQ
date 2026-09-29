"""Tests for the catalog-overview dashboard (stat tiles, bar charts, donut chart)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)
from src.gui import application
from src.gui.application import PsyMetriQApplication


class FakePage:
    def __init__(self) -> None:
        self.services: list[Any] = []
        self.window = SimpleNamespace(min_width=None, min_height=None)
        self.controls: list[Any] = []
        self.update_count = 0
        self.dialogs: list[Any] = []

    def add(self, *controls: Any) -> None:
        self.controls.extend(controls)

    def update(self, *_controls: Any) -> None:
        self.update_count += 1

    def show_dialog(self, dialog: Any) -> None:
        self.dialogs.append(dialog)

    def pop_dialog(self) -> Any:
        return self.dialogs.pop() if self.dialogs else None


def _family(
    instrument_id: str, *, language: str, keywords: list[str], item_text_included: bool
) -> QuestionnaireParent:
    if item_text_included:
        version = QuestionnaireVersion(
            version_id="v1",
            language=language,
            response_sets={
                "s": [
                    ResponseOption(code=0, label="No", score=0),
                    ResponseOption(code=1, label="Yes", score=1),
                ]
            },
            items=[
                ItemSchema(
                    item_id="q1",
                    variable_name="q1",
                    dimension="core",
                    prompt_text="Demo item",
                    response_set_ref="s",
                ),
                ItemSchema(
                    item_id="q2",
                    variable_name="q2",
                    dimension="core",
                    prompt_text="Second demo item",
                    response_set_ref="s",
                ),
            ],
            metadata=QuestionnaireMetadata(keywords=keywords),
        )
    else:
        version = QuestionnaireVersion(
            version_id="v1",
            language=language,
            item_text_included=False,
            source_reported_item_count=5,
            metadata=QuestionnaireMetadata(keywords=keywords),
        )
    return QuestionnaireParent(
        instrument_id=instrument_id,
        name_full=instrument_id,
        is_commercial=False,
        versions=[version],
    )


def _app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PsyMetriQApplication:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", tmp_path / "admin_config.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    family_a = _family("a", language="de", keywords=["stress", "angst"], item_text_included=True)
    family_b = _family("b", language="de", keywords=["stress"], item_text_included=True)
    family_c = _family("c", language="en", keywords=["wellbeing"], item_text_included=False)
    app.catalog_records = [
        (family_a, Path("a.json")),
        (family_b, Path("b.json")),
        (family_c, Path("c.json")),
    ]
    return app


def test_overview_panel_counts_instruments_items_languages_and_topics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)

    panel = app._catalog_overview_panel()

    assert panel.subtitle == "3 Instrumente · 4 Items · 2 Sprachen · 3 Themen"


def test_overview_panel_stat_tiles_show_the_same_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)

    panel = app._catalog_overview_panel()
    inner_column = panel.controls[0]
    stat_row = inner_column.controls[0]
    values = [
        tile.content.controls[1].value for tile in stat_row.controls
    ]

    assert values == ["3", "4", "2", "3"]


def test_bar_chart_renders_one_row_per_entry_in_the_given_order() -> None:
    """_bar_chart renders whatever order it's given; sorting/limiting is the caller's job."""
    chart = PsyMetriQApplication._bar_chart(
        "Test", [("a", 1), ("b", 5), ("c", 3)], color="#000000"
    )

    bar_labels = [row.controls[0].content.value for row in chart.controls[1:]]
    assert bar_labels == ["a", "b", "c"]


def test_overview_panel_sorts_topics_by_instrument_count_descending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)

    panel = app._catalog_overview_panel()
    charts_row = panel.controls[0].controls[1]
    topics_chart = charts_row.controls[1]
    topic_labels = [row.controls[0].content.value for row in topics_chart.controls[1:]]

    assert topic_labels[0] == "stress"  # appears in 2 of 3 instruments, the others in 1 each


def test_bar_chart_handles_empty_input_without_raising() -> None:
    chart = PsyMetriQApplication._bar_chart("Test", [])

    assert "keine Daten" in chart.value


def test_donut_chart_computes_percentages_and_avoids_division_by_zero() -> None:
    chart = PsyMetriQApplication._donut_chart(
        "Ratio", [("with", 3, "#111111"), ("without", 1, "#222222")]
    )
    legend_texts = [row.controls[1].value for row in chart.controls[1].controls[1].controls]

    assert legend_texts == ["with: 3 (75%)", "without: 1 (25%)"]


def test_donut_chart_handles_all_zero_segments_without_raising() -> None:
    chart = PsyMetriQApplication._donut_chart("Empty", [("a", 0, "#111111"), ("b", 0, "#222222")])

    legend_texts = [row.controls[1].value for row in chart.controls[1].controls[1].controls]
    assert legend_texts == ["a: 0", "b: 0"]
