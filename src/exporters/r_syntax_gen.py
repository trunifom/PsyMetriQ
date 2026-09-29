"""Generate base-R syntax for the scoring workflow a questionnaire version documents.

The generated script assumes a data.frame ``df`` already holds one column
per item ``variable_name`` (for example imported from a REDCap/Qualtrics/CSV
export using those exact names) and attaches variable labels plus one score
column per documented ``ScoringAlgorithm``. It uses only base R (no
``dplyr``/``sjlabelled``/``car`` dependency) so it runs in any R
installation without an extra package.

Like every other exporter in this project, this is a translation of already
validated PsyMetriQ data; it is not a validated clinical scoring engine and
does not replace the source publisher's manual. Reverse-scored or otherwise
non-identity-coded items are recoded explicitly via each response option's
``score`` (never the raw stored code), exactly as the REDCap ``calc`` field
export in ``data_exchange.py`` already does, so the two exporters cannot
silently compute different totals for the same instrument.
"""

from __future__ import annotations

import re
from datetime import date

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
    ScoringAlgorithm,
)


def _r_string_literal(value: str) -> str:
    """Escape a Python string as a safe, single-line double-quoted R literal."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )
    return f'"{escaped}"'


def _r_number(value: float) -> str:
    """Render a number without a spurious trailing ``.0`` for whole numbers."""
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _r_code_key(code: str | int) -> str:
    """Render a response code as the character key ``as.character()`` would produce."""
    if isinstance(code, bool):
        return "1" if code else "0"
    if isinstance(code, int):
        return str(code)
    try:
        numeric = float(code)
    except (TypeError, ValueError):
        return str(code)
    return _r_number(numeric)


def _safe_r_name(value: str, fallback: str) -> str:
    """Sanitize free text into a safe, backtick-free R identifier."""
    normalized = re.sub(r"[^A-Za-z0-9_.]+", "_", value.strip()).strip("_")
    if not normalized or not (normalized[0].isalpha()):
        normalized = f"{fallback}_{normalized}" if normalized else fallback
    return normalized or fallback


def _item_scored_expression(
    item: ItemSchema, response_sets: dict[str, list[ResponseOption]]
) -> tuple[list[str], str]:
    """Return (setup lines, R expression) for one item's numeric scored contribution.

    When every response option's stored code already equals its score, the
    raw column is used directly; otherwise a named lookup vector recodes
    each stored value to its documented ``ResponseOption.score`` explicitly.
    ``item.is_reverse_scored`` is then applied on top of either path, using
    the standard ``(min + max) - value`` reversal over that response set's
    own score range: catalog response sets record each option's
    forward-direction score once and are shared by both forward-keyed and
    reverse-keyed items (see the Rosenberg Self-Esteem Scale), so the score
    field alone does not already encode reversal.
    """
    variable = item.variable_name
    if item.response_mode != "categorical" or not item.response_set_ref:
        return [], f"df${variable}"
    options = response_sets.get(item.response_set_ref, [])
    scored_options = [option for option in options if option.score is not None]
    if not scored_options:
        return [], f"df${variable}"

    def _code_matches_score(option: ResponseOption) -> bool:
        try:
            return float(option.code) == option.score
        except (TypeError, ValueError):
            return False

    if len(scored_options) == len(options) and all(
        _code_matches_score(option) for option in scored_options
    ):
        setup: list[str] = []
        expression = f"df${variable}"
    else:
        recode_vector = f".recode_{variable}"
        pairs = ", ".join(
            f"`{_r_code_key(option.code)}` = {_r_number(option.score)}"
            for option in scored_options
        )
        setup = [f"{recode_vector} <- c({pairs})"]
        expression = f"unname({recode_vector}[as.character(df${variable})])"

    if item.is_reverse_scored:
        score_values = [option.score for option in scored_options]
        reversal_sum = _r_number(min(score_values) + max(score_values))
        expression = f"({reversal_sum} - ({expression}))"
    return setup, expression


def _scoring_block(algorithm: ScoringAlgorithm, version: QuestionnaireVersion) -> list[str]:
    items_by_id = {item.item_id: item for item in version.items}
    ordered_items = [
        items_by_id[item_id] for item_id in algorithm.target_items if item_id in items_by_id
    ]
    header = f"# --- Score: {algorithm.output_variable} ({algorithm.method}"
    if algorithm.missing_data_rules:
        header += f"; missing data: {algorithm.missing_data_rules}"
    header += ") ---"
    lines = [header]
    if not ordered_items:
        lines.append(f"# No target items resolved for {algorithm.output_variable!r}; skipped.")
        return lines

    expressions: list[str] = []
    for item in ordered_items:
        setup, expression = _item_scored_expression(item, version.response_sets)
        lines.extend(setup)
        expressions.append(expression)

    combined = "cbind(" + ", ".join(expressions) + ")"
    aggregate = (
        f"rowMeans({combined}, na.rm = TRUE)"
        if algorithm.method == "mean"
        else f"rowSums({combined}, na.rm = TRUE)"
    )
    if algorithm.multiplier != 1:
        aggregate = f"({aggregate}) * {_r_number(algorithm.multiplier)}"

    output_name = _safe_r_name(algorithm.output_variable, "score")
    lines.append(f"df${output_name} <- {aggregate}")
    return lines


def export_r_syntax(questionnaire: QuestionnaireParent, version: QuestionnaireVersion) -> str:
    """Generate a base-R script implementing this version's documented scoring."""
    lines: list[str] = [
        "# R scoring syntax generated by PsyMetriQ",
        f"# Instrument: {questionnaire.name_full} ({questionnaire.instrument_id})",
        f"# Version: {version.version_id} ({version.language})",
        f"# Generated: {date.today().isoformat()}",
        "#",
        "# This script implements the scoring workflow this catalogue documents. It is",
        "# not a validated clinical scoring engine and does not replace the official",
        "# manual; verify results against the source publisher before use in analysis.",
        "#",
        "# Expected input: a data.frame named `df` with one column per variable name",
        "# below (e.g. imported from a REDCap/Qualtrics/CSV export using these names).",
        "",
    ]
    if version.items:
        lines.append("# --- Variable labels ---")
        for item in version.items:
            lines.append(
                f'attr(df${item.variable_name}, "label") <- {_r_string_literal(item.prompt_text)}'
            )
        lines.append("")
    if not version.scoring_algorithms:
        lines.append("# No scoring algorithms are documented for this version.")
        return "\n".join(lines) + "\n"
    for algorithm in version.scoring_algorithms:
        lines.extend(_scoring_block(algorithm, version))
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
