"""Tests for the standalone dashboard rendering module (src/gui/views/dashboard.py).

These call the module's plain functions directly rather than going through
PsyMetriQApplication, since bar_chart/donut_chart take only their own
arguments and hold no GUI session state -- exactly the decomposition
boundary this module exists to demonstrate.
"""

from src.gui.views.dashboard import bar_chart, donut_chart


def test_bar_chart_renders_one_row_per_entry_in_the_given_order() -> None:
    """bar_chart renders whatever order it's given; sorting/limiting is the caller's job."""
    chart = bar_chart("Test", [("a", 1), ("b", 5), ("c", 3)], color="#000000")

    bar_labels = [row.controls[0].content.value for row in chart.controls[1:]]
    assert bar_labels == ["a", "b", "c"]


def test_bar_chart_handles_empty_input_without_raising() -> None:
    chart = bar_chart("Test", [])

    assert "keine Daten" in chart.value


def test_donut_chart_computes_percentages_and_avoids_division_by_zero() -> None:
    chart = donut_chart("Ratio", [("with", 3, "#111111"), ("without", 1, "#222222")])
    legend_texts = [row.controls[1].value for row in chart.controls[1].controls[1].controls]

    assert legend_texts == ["with: 3 (75%)", "without: 1 (25%)"]


def test_donut_chart_handles_all_zero_segments_without_raising() -> None:
    chart = donut_chart("Empty", [("a", 0, "#111111"), ("b", 0, "#222222")])

    legend_texts = [row.controls[1].value for row in chart.controls[1].controls[1].controls]
    assert legend_texts == ["a: 0", "b: 0"]
