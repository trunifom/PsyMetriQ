"""Catalog-overview dashboard: stat tiles, bar charts, and a donut chart.

First step of the GUI decomposition ``docs/architecture.md`` reserves
``src/gui/views/``/``src/gui/viewmodels/`` for: a self-contained rendering
module with no dependency on ``PsyMetriQApplication`` beyond the catalog
records it is handed. It reads state (the loaded catalogue) and renders a
control tree; it dispatches no user intent and holds no session state of its
own, matching the MVVM boundary ``docs/architecture.md`` describes.

This Flet version (1.0.1) ships no chart controls, so every visual here is
built from plain Flet primitives: proportional-width ``Container``s for the
bars, and a ``SweepGradient``-based ring for the donut. No charting library
was added for this.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from schemas.questionnaire_schema import QuestionnaireParent


def _icon(name: str) -> Any:
    """Resolve an optional icon name across Flet/Material icon-set revisions."""
    return getattr(ft.Icons, name, ft.Icons.INFO_OUTLINE)


def stat_tile(label: str, value: int, icon_name: str) -> ft.Control:
    return ft.Container(
        width=170,
        bgcolor="#F7F9F8",
        border_radius=10,
        padding=14,
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(_icon(icon_name), color="#28685D", size=18),
                        ft.Text(label, size=12, color="#55716A"),
                    ],
                ),
                ft.Text(str(value), size=26, weight=ft.FontWeight.BOLD, color="#173D36"),
            ],
        ),
    )


def horizontal_bar_row(
    label: str, count: int, maximum: int, *, color: str = "#28685D", track_width: int = 180
) -> ft.Control:
    """A single labeled, proportional-width bar; no charting library required."""
    fraction = (count / maximum) if maximum > 0 else 0.0
    fill_width = max(3, round(track_width * fraction))
    return ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=140,
                content=ft.Text(
                    label, size=12, color="#173D36", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS
                ),
            ),
            ft.Container(
                width=track_width,
                height=14,
                bgcolor="#E8EFEC",
                border_radius=4,
                content=ft.Container(width=fill_width, height=14, bgcolor=color, border_radius=4),
            ),
            ft.Text(str(count), size=12, color="#55716A"),
        ],
    )


def bar_chart(title: str, entries: list[tuple[str, int]], *, color: str = "#28685D") -> ft.Control:
    if not entries:
        return ft.Text(f"{title}: keine Daten", size=12, color="#55716A")
    maximum = max(count for _label, count in entries)
    return ft.Column(
        spacing=6,
        controls=[
            ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="#173D36"),
            *(
                horizontal_bar_row(label, count, maximum, color=color)
                for label, count in entries
            ),
        ],
    )


def donut_chart(
    title: str,
    segments: list[tuple[str, int, str]],
    *,
    size: int = 120,
    hole_ratio: float = 0.55,
) -> ft.Control:
    """A ring chart built from a SweepGradient; avoids a third-party chart library."""
    total = sum(count for _label, count, _color in segments)
    legend = ft.Column(
        spacing=4,
        controls=[
            ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(width=10, height=10, bgcolor=color, border_radius=3),
                    ft.Text(
                        f"{label}: {count} ({(count / total * 100):.0f}%)"
                        if total
                        else f"{label}: 0",
                        size=12,
                        color="#55716A",
                    ),
                ],
            )
            for label, count, color in segments
        ],
    )
    if not total:
        ring: ft.Control = ft.Container(
            width=size,
            height=size,
            shape=ft.BoxShape.CIRCLE,
            bgcolor="#E8EFEC",
        )
    else:
        colors: list[str] = []
        stops: list[float] = []
        cumulative = 0.0
        for label, count, color in segments:
            fraction = count / total
            colors.extend([color, color])
            stops.extend([cumulative, cumulative + fraction])
            cumulative += fraction
        ring = ft.Container(
            width=size,
            height=size,
            shape=ft.BoxShape.CIRCLE,
            gradient=ft.SweepGradient(colors=colors, stops=stops),
            content=ft.Container(
                width=size * hole_ratio,
                height=size * hole_ratio,
                shape=ft.BoxShape.CIRCLE,
                bgcolor="#F7F9F8",
                alignment=ft.Alignment.CENTER,
                content=ft.Text(str(total), size=16, weight=ft.FontWeight.BOLD, color="#173D36"),
            ),
            alignment=ft.Alignment.CENTER,
        )
    return ft.Column(
        spacing=8,
        controls=[
            ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="#173D36"),
            ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[ring, legend],
            ),
        ],
    )


def build_catalog_overview_panel(
    catalog_records: list[tuple[QuestionnaireParent, Path]],
) -> ft.Control:
    """A dashboard summarizing the whole catalog, independent of active filters."""
    instrument_count = len(catalog_records)
    item_count = 0
    language_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    item_bearing_versions = 0
    reference_only_versions = 0
    for family, _path in catalog_records:
        family_topics = {keyword for keyword in family.metadata.keywords if keyword.strip()}
        for version in family.versions:
            item_count += len(version.items)
            language_counts[version.language] = language_counts.get(version.language, 0) + 1
            if version.item_text_included:
                item_bearing_versions += 1
            else:
                reference_only_versions += 1
            family_topics |= {keyword for keyword in version.metadata.keywords if keyword.strip()}
        for topic in family_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    top_languages = sorted(language_counts.items(), key=lambda entry: entry[1], reverse=True)[:6]
    top_topics = sorted(topic_counts.items(), key=lambda entry: entry[1], reverse=True)[:8]

    charts = ft.Row(
        spacing=28,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            bar_chart("Sprachen (nach Versionen)", top_languages, color="#28685D"),
            bar_chart("Häufigste Themen", top_topics, color="#3E7C6F"),
            donut_chart(
                "Itemtext vs. Referenz",
                [
                    ("Mit Itemtext", item_bearing_versions, "#28685D"),
                    ("Nur Referenz", reference_only_versions, "#B9CFC8"),
                ],
            ),
        ],
    )
    return ft.ExpansionTile(
        title="Katalog-Übersicht",
        subtitle=(
            f"{instrument_count} Instrumente · {item_count} Items · "
            f"{len(language_counts)} Sprachen · {len(topic_counts)} Themen"
        ),
        expanded=True,
        maintain_state=True,
        bgcolor="#F7F9F8",
        collapsed_bgcolor="#EEF3F1",
        controls=[
            ft.Column(
                spacing=16,
                controls=[
                    ft.Row(
                        spacing=12,
                        wrap=True,
                        controls=[
                            stat_tile("Instrumente", instrument_count, "LIBRARY_BOOKS"),
                            stat_tile("Items", item_count, "CHECKLIST"),
                            stat_tile("Sprachen", len(language_counts), "LANGUAGE"),
                            stat_tile("Themen", len(topic_counts), "SELL"),
                        ],
                    ),
                    charts,
                ],
            ),
        ],
    )
