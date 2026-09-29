"""Estimate respondent completion time for one version or a selected battery.

Two estimation paths, always kept distinguishable so a caller never presents
a heuristic as if it were a validated figure:

- **Source-reported**: parsed from ``QuestionnaireVersion.administration_time``,
  the curated, source-grounded free text already in the catalog (for example
  ``"ca. 5-10 Minuten"``). Parsing only recognizes the catalog's existing
  conventions and returns ``None`` rather than guessing when no number can be
  found (for example ``"formabhaengig; Quelle konsultieren"``).
- **Heuristic**: a deliberately wide seconds-per-item range keyed by response
  mode, used only when no source-reported time is available. This is a rough
  planning aid, not a citation-backed constant; it is always labelled as an
  estimate rather than a source-reported fact.

When neither path yields a number the result is explicitly "unknown" rather
than silently treated as zero, so a battery total never understates itself
by dropping an instrument it could not estimate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from schemas.questionnaire_schema import ItemSchema, QuestionnaireParent, QuestionnaireVersion

TimeEstimateSource = Literal["source_reported", "heuristic_item_count", "unknown"]

# A deliberately wide, non-citation planning range (seconds) per response mode,
# reflecting typical short self-report survey items; not a validated constant.
_SECONDS_PER_ITEM_RANGE: dict[str, tuple[float, float]] = {
    "categorical": (4.0, 10.0),
    "numeric": (5.0, 12.0),
    "text": (15.0, 40.0),
}
_DEFAULT_SECONDS_PER_ITEM_RANGE = (5.0, 12.0)

_RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:bis|-|–)\s*(\d+(?:[.,]\d+)?)\s*min", re.IGNORECASE)
_UNDER_RE = re.compile(r"unter\s+(\d+(?:[.,]\d+)?)\s*min", re.IGNORECASE)
_SINGLE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*min", re.IGNORECASE)


@dataclass
class VersionTimeEstimate:
    """One version's estimated completion time and how it was derived."""

    instrument_id: str
    version_id: str
    label: str
    minimum_minutes: float | None
    maximum_minutes: float | None
    source: TimeEstimateSource
    detail: str


@dataclass
class BatteryTimeEstimate:
    """Aggregated completion-time estimate for a selected battery of versions."""

    entries: list[VersionTimeEstimate] = field(default_factory=list)

    @property
    def minimum_minutes(self) -> float | None:
        known = [
            entry.minimum_minutes for entry in self.entries if entry.minimum_minutes is not None
        ]
        return round(sum(known), 1) if known else None

    @property
    def maximum_minutes(self) -> float | None:
        known = [
            entry.maximum_minutes for entry in self.entries if entry.maximum_minutes is not None
        ]
        return round(sum(known), 1) if known else None

    @property
    def has_unknown_entries(self) -> bool:
        return any(entry.source == "unknown" for entry in self.entries)


def parse_administration_time(text: str | None) -> tuple[float, float] | None:
    """Parse a source-reported administration time into a (minimum, maximum) minute range.

    Recognizes the catalog's existing conventions (``"ca. 5-10 Minuten"``,
    ``"unter 2 Minuten"``, ``"ca. 5 Minuten"``). Returns ``None`` rather than
    guessing when no numeric time can be found in the text.
    """
    if not text:
        return None
    range_match = _RANGE_RE.search(text)
    if range_match:
        low = float(range_match.group(1).replace(",", "."))
        high = float(range_match.group(2).replace(",", "."))
        return (min(low, high), max(low, high))
    under_match = _UNDER_RE.search(text)
    if under_match:
        high = float(under_match.group(1).replace(",", "."))
        return (0.0, high)
    single_match = _SINGLE_RE.search(text)
    if single_match:
        value = float(single_match.group(1).replace(",", "."))
        return (value, value)
    return None


def _heuristic_seconds_for_items(items: list[ItemSchema]) -> tuple[float, float]:
    low = sum(
        _SECONDS_PER_ITEM_RANGE.get(item.response_mode, _DEFAULT_SECONDS_PER_ITEM_RANGE)[0]
        for item in items
    )
    high = sum(
        _SECONDS_PER_ITEM_RANGE.get(item.response_mode, _DEFAULT_SECONDS_PER_ITEM_RANGE)[1]
        for item in items
    )
    return low, high


def estimate_version_time(
    questionnaire: QuestionnaireParent,
    version: QuestionnaireVersion,
    item_ids: list[str] | None = None,
) -> VersionTimeEstimate:
    """Estimate one version's completion time.

    Prefers a parseable source-reported ``administration_time``, which always
    describes the complete form. ``item_ids`` narrows the heuristic fallback
    to a selected item subset (empty/``None`` means the complete version) and
    has no effect once a source-reported time is used.
    """
    label = f"{questionnaire.name_full} ({version.display_name or version.version_id})"
    parsed = parse_administration_time(version.administration_time)
    if parsed is not None:
        return VersionTimeEstimate(
            instrument_id=questionnaire.instrument_id,
            version_id=version.version_id,
            label=label,
            minimum_minutes=parsed[0],
            maximum_minutes=parsed[1],
            source="source_reported",
            detail=version.administration_time or "",
        )

    items = version.items
    if item_ids:
        selected_ids = set(item_ids)
        items = [item for item in items if item.item_id in selected_ids]
    if items:
        low_seconds, high_seconds = _heuristic_seconds_for_items(items)
        return VersionTimeEstimate(
            instrument_id=questionnaire.instrument_id,
            version_id=version.version_id,
            label=label,
            minimum_minutes=round(low_seconds / 60, 1),
            maximum_minutes=round(high_seconds / 60, 1),
            source="heuristic_item_count",
            detail=(
                f"Grobschaetzung aus {len(items)} ausgewaehlten Item(s) je nach Antwortformat "
                "(keine Quellenangabe zur Bearbeitungszeit hinterlegt)."
            ),
        )
    if version.source_reported_item_count:
        low_per, high_per = _DEFAULT_SECONDS_PER_ITEM_RANGE
        count = version.source_reported_item_count
        return VersionTimeEstimate(
            instrument_id=questionnaire.instrument_id,
            version_id=version.version_id,
            label=label,
            minimum_minutes=round(count * low_per / 60, 1),
            maximum_minutes=round(count * high_per / 60, 1),
            source="heuristic_item_count",
            detail=(
                f"Grobschaetzung aus quellenberichteter Itemanzahl ({count}); "
                "Antwortformat der einzelnen Items ist nicht bekannt."
            ),
        )
    return VersionTimeEstimate(
        instrument_id=questionnaire.instrument_id,
        version_id=version.version_id,
        label=label,
        minimum_minutes=None,
        maximum_minutes=None,
        source="unknown",
        detail=(
            "Weder eine Quellenangabe zur Bearbeitungszeit noch eine bekannte Itemanzahl vorhanden."
        ),
    )


def estimate_battery_time(
    selections: list[tuple[QuestionnaireParent, QuestionnaireVersion, list[str]]],
) -> BatteryTimeEstimate:
    """Estimate total completion time for a selected battery of (family, version, item_ids)."""
    return BatteryTimeEstimate(
        entries=[
            estimate_version_time(family, version, item_ids)
            for family, version, item_ids in selections
        ]
    )
