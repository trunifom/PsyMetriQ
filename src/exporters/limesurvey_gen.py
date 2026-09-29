"""Best-effort LimeSurvey TSV survey-structure export/import.

LimeSurvey's own manual describes its TSV/"Structure" format only partially:
a fixed set of 14 leading columns, "followed by alphabetically-ordered
database field names" whose exact set is genuinely version-dependent. To
avoid guessing at that version-dependent tail, this module was built and
verified directly against ``TSVImportSurvey()`` in
``application/helpers/admin/import_helper.php`` on the LimeSurvey ``master``
branch (fetched 2026-09-29): only the fixed columns that function actually
reads are used here, and its own code tolerates any other missing/unknown
column by defaulting it to empty. That import function requires only
``class``, ``name``, and ``text`` to be present as headers; every other
column is optional there.

This still has **not been verified against a live LimeSurvey instance** --
unlike this project's REDCap support, which was checked against PyCap's
real API. Test-import a generated file into a real (or trial) LimeSurvey
installation before relying on it for an actual study, exactly as you
would review a generated R script or REDCap Data Dictionary before use.

Supported LimeSurvey question types (see
https://www.limesurvey.org/manual/Question_object_types): ``L`` (List
Radio) and ``M`` (Multiple choice) for categorical items, ``N`` (Numerical
Input) for numeric items (including a slider-typed item -- LimeSurvey's own
slider widget is not produced), and ``S`` (Short Free Text) for text items.
Branching (``show_if``) is rendered as a LimeSurvey ExpressionScript
relevance equation (``Q1 == "A1" and Q2 != "A2"``); this syntax is common
LimeSurvey usage but -- like everything else here -- should be confirmed in
a test import.
"""

from __future__ import annotations

import csv
import io
import re

from pydantic import ValidationError

from schemas.questionnaire_schema import (
    BranchingCondition,
    ItemSchema,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)

_LIMESURVEY_RESPONDENT_TYPES = frozenset({"L", "M", "N", "S"})
_LIMESURVEY_RELEVANCE_CONDITION_RE = re.compile(
    r'^(?P<field>[A-Za-z][A-Za-z0-9_]*)\s*(?P<operator>==|!=)\s*"(?P<value>(?:[^"\\]|\\.)*)"$'
)

LIMESURVEY_TSV_HEADERS = [
    "id",
    "related_id",
    "class",
    "type/scale",
    "name",
    "relevance",
    "text",
    "help",
    "language",
    "validation",
    "mandatory",
    "other",
    "default",
    "assessment_value",
]


class LimeSurveyExportError(RuntimeError):
    """Raised when a questionnaire version cannot be rendered as LimeSurvey rows."""


class LimeSurveyImportError(RuntimeError):
    """Raised when LimeSurvey TSV content is malformed or has no importable rows."""


def _safe_identifier(value: str, fallback: str, *, max_length: int = 40) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    if not normalized or not normalized[0].isalpha():
        normalized = f"{fallback}_{normalized}" if normalized else fallback
    return normalized[:max_length].rstrip("_") or fallback


def _safe_variable_name(value: str, index: int, *, max_length: int = 20) -> str:
    """Sanitize into a LimeSurvey-safe question code (letters/digits, capped length)."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"q_{normalized}" if normalized else f"q{index:03d}"
    return normalized[:max_length].rstrip("_") or f"q{index:03d}"


def _limesurvey_question_type(item: ItemSchema) -> str:
    if item.response_mode == "categorical":
        return "M" if item.redcap_field_type == "checkbox" else "L"
    if item.response_mode == "numeric":
        return "N"
    return "S"


def _limesurvey_relevance(item: ItemSchema, items_by_id: dict[str, ItemSchema]) -> str:
    """Render show_if as a LimeSurvey ExpressionScript relevance equation."""
    if not item.show_if:
        return "1"
    parts: list[str] = []
    for condition in item.show_if:
        source_item = items_by_id.get(condition.source_item_id)
        if source_item is None:
            continue
        operator = "==" if condition.operator == "equals" else "!="
        value = condition.value.replace('"', '\\"')
        parts.append(f'{source_item.variable_name} {operator} "{value}"')
    return "(" + " and ".join(parts) + ")" if parts else "1"


def build_limesurvey_rows(
    questionnaire: QuestionnaireParent, version: QuestionnaireVersion
) -> list[dict[str, str]]:
    """Build LimeSurvey TSV rows (S/SL/G/Q/A classes) for one questionnaire version."""
    if not version.items:
        raise LimeSurveyExportError("This version has no items to export")
    items_by_id = {item.item_id: item for item in version.items}
    rows: list[dict[str, str]] = [
        {"class": "S", "name": "language", "text": version.language},
        {
            "class": "SL",
            "language": version.language,
            "name": "surveyls_title",
            "text": f"{questionnaire.name_full} ({version.version_id})",
        },
    ]

    group_ids: dict[str, int] = {}
    for item in version.items:
        if item.dimension not in group_ids:
            group_ids[item.dimension] = len(group_ids) + 1
            rows.append(
                {
                    "class": "G",
                    "name": item.dimension,
                    "language": version.language,
                    "text": item.dimension,
                }
            )

    for item in version.items:
        field_type = _limesurvey_question_type(item)
        rows.append(
            {
                "class": "Q",
                "type/scale": field_type,
                "name": item.variable_name,
                "relevance": _limesurvey_relevance(item, items_by_id),
                "text": item.prompt_text,
                "help": item.measurement_unit or "",
                "language": version.language,
                "mandatory": "Y" if item.is_required else "N",
            }
        )
        if item.response_mode != "categorical" or not item.response_set_ref:
            continue
        for option in version.response_sets.get(item.response_set_ref, []):
            answer_row = {
                "class": "A",
                "type/scale": "0",
                "name": str(option.code),
                "text": option.label,
                "language": version.language,
            }
            if option.score is not None:
                answer_row["assessment_value"] = str(round(option.score))
            rows.append(answer_row)

    return rows


def export_limesurvey_tsv(questionnaire: QuestionnaireParent, version: QuestionnaireVersion) -> str:
    """Render one questionnaire version as a LimeSurvey-importable TSV document."""
    rows = build_limesurvey_rows(questionnaire, version)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=LIMESURVEY_TSV_HEADERS, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in LIMESURVEY_TSV_HEADERS})
    return output.getvalue()


def _parse_limesurvey_relevance(
    raw: str, variable_to_item_id: dict[str, str], *, own_item_id: str
) -> list[BranchingCondition] | None:
    """Parse a plain ``(A == "x" and B != "y")`` relevance equation, or return None.

    Mirrors ``_parse_redcap_branching_logic`` in ``data_exchange.py``: never
    raises, and refuses (returning ``None``) anything with ``or``, nested
    parentheses, or a reference to a field outside this file, rather than
    guessing at LimeSurvey's full ExpressionScript grammar.
    """
    text = raw.strip()
    if text in ("", "1"):
        return []
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    lowered = text.casefold()
    if " or " in lowered or "(" in text or ")" in text:
        return None
    conditions: list[BranchingCondition] = []
    for part in re.split(r"\s+and\s+", text, flags=re.IGNORECASE):
        match = _LIMESURVEY_RELEVANCE_CONDITION_RE.match(part.strip())
        if match is None:
            return None
        source_item_id = variable_to_item_id.get(match.group("field"))
        if source_item_id is None or source_item_id == own_item_id:
            return None
        conditions.append(
            BranchingCondition(
                source_item_id=source_item_id,
                operator="equals" if match.group("operator") == "==" else "not_equals",
                value=match.group("value").replace('\\"', '"'),
            )
        )
    return conditions


def import_limesurvey_tsv(content: str, *, default_language: str = "en") -> QuestionnaireParent:
    """Import a LimeSurvey TSV survey-structure export as a PsyMetriQ questionnaire.

    Only ``L``/``M``/``N``/``S`` questions become respondent items. Other
    LimeSurvey question types are never silently dropped: each is listed by
    name/type in the imported instrument's ``metadata.notes``. A relevance
    equation is parsed back into ``show_if`` only when it is a plain
    ``and``-chain of ``field == "value"``/``field != "value"`` conditions
    resolvable within this file; anything else is preserved verbatim in that
    item's own notes instead of being guessed at.
    """
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("﻿")), delimiter="\t")
        rows = list(reader)
    except csv.Error as error:
        raise LimeSurveyImportError("Could not read LimeSurvey TSV content") from error
    if not reader.fieldnames or not {"class", "name", "text"}.issubset(reader.fieldnames):
        raise LimeSurveyImportError(
            "The file does not look like a valid LimeSurvey TSV export "
            "(missing required class/name/text columns)"
        )

    language = default_language
    survey_title: str | None = None
    group_names: dict[int, str] = {}
    group_order: list[int] = []
    current_group_index = -1
    current_question_id: str | None = None
    current_question_type: str | None = None
    response_sets: dict[str, list[ResponseOption]] = {}
    items: list[ItemSchema] = []
    raw_relevance: dict[str, str] = {}
    skipped_questions: list[str] = []
    used_variable_names: set[str] = set()
    used_item_ids: set[str] = set()

    for index, row in enumerate(rows, start=1):
        row_class = (row.get("class") or "").strip()
        if row_class == "S":
            if (row.get("name") or "").strip() == "language" and row.get("text"):
                language = row["text"].strip() or language
            continue
        if row_class == "SL":
            if (row.get("name") or "").strip() == "surveyls_title":
                survey_title = (row.get("text") or "").strip() or survey_title
            continue
        if row_class == "G":
            current_group_index += 1
            group_order.append(current_group_index)
            group_names[current_group_index] = (
                row.get("name") or row.get("text") or ""
            ).strip() or (f"group_{current_group_index + 1}")
            continue
        if row_class == "Q":
            field_type = (row.get("type/scale") or "").strip() or "S"
            source_name = (row.get("name") or "").strip()
            if field_type not in _LIMESURVEY_RESPONDENT_TYPES:
                skipped_questions.append(f"{source_name or index} (type {field_type or 'unknown'})")
                current_question_id = None
                current_question_type = None
                continue
            variable_name = _safe_variable_name(source_name, index)
            if variable_name.casefold() in used_variable_names:
                suffix = f"_{index}"
                variable_name = variable_name[: max(1, 20 - len(suffix))].rstrip("_") + suffix
            used_variable_names.add(variable_name.casefold())
            item_id = _safe_identifier(source_name or f"item_{index:03d}", "item")
            if item_id in used_item_ids:
                suffix = f"_{index}"
                item_id = item_id[: max(1, 40 - len(suffix))].rstrip("_") + suffix
            used_item_ids.add(item_id)
            mode = (
                "categorical"
                if field_type in ("L", "M")
                else "numeric"
                if field_type == "N"
                else "text"
            )
            response_ref = f"limesurvey_scale_{index:03d}" if mode == "categorical" else None
            if response_ref:
                response_sets[response_ref] = []
            group_name = group_names.get(current_group_index, "general")
            raw_relevance[item_id] = (row.get("relevance") or "").strip()
            items.append(
                ItemSchema(
                    item_id=item_id,
                    variable_name=variable_name,
                    dimension=group_name,
                    prompt_text=(row.get("text") or "").strip(),
                    response_mode=mode,
                    response_set_ref=response_ref,
                    is_required=(row.get("mandatory") or "").strip().upper() == "Y",
                    measurement_unit=(row.get("help") or None),
                    redcap_field_type="checkbox" if field_type == "M" else "radio",
                )
            )
            current_question_id = item_id
            current_question_type = field_type
            continue
        if row_class == "A":
            if current_question_id is None or current_question_type not in ("L", "M"):
                continue
            response_ref = next(
                (item.response_set_ref for item in items if item.item_id == current_question_id),
                None,
            )
            if response_ref is None:
                continue
            code = (row.get("name") or "").strip()
            score_text = (row.get("assessment_value") or "").strip()
            try:
                score = float(score_text) if score_text else None
            except ValueError:
                score = None
            label = (row.get("text") or "").strip() or code
            response_sets[response_ref].append(
                ResponseOption(
                    code=code or f"opt_{len(response_sets[response_ref])}",
                    label=label,
                    score=score,
                )
            )
            continue
        # Any other class (AS/QTA/QTAM/QTALS/C/unknown) is not represented; skip silently,
        # matching LimeSurvey's own importer, which only acts on recognized classes.

    if not items:
        raise LimeSurveyImportError("LimeSurvey TSV content contains no importable questions")

    variable_to_item_id = {item.variable_name: item.item_id for item in items}
    resolved_items: list[ItemSchema] = []
    for item in items:
        notes: list[str] = [item.metadata.notes] if item.metadata.notes else []
        updates: dict[str, object] = {}

        # A categorical question with no parsed answer options cannot reference a
        # response set; downgrade it to free text rather than fail the whole import.
        if item.response_set_ref is not None and not response_sets.get(item.response_set_ref):
            updates["response_mode"] = "text"
            updates["response_set_ref"] = None
            notes.append(
                "Imported as free text: no LimeSurvey answer (class 'A') rows were "
                "found for this question."
            )

        raw = raw_relevance.get(item.item_id, "")
        conditions = _parse_limesurvey_relevance(raw, variable_to_item_id, own_item_id=item.item_id)
        if conditions is not None:
            if conditions:
                updates["show_if"] = conditions
        else:
            notes.append(f"Original LimeSurvey relevance equation (not structurally parsed): {raw}")

        if notes:
            updates["metadata"] = item.metadata.model_copy(update={"notes": "\n".join(notes)})
        resolved_items.append(item.model_copy(update=updates) if updates else item)

    family_notes = (
        f"Fields present in the LimeSurvey export but not imported as respondent items "
        f"(unsupported question type): {'; '.join(skipped_questions)}"
        if skipped_questions
        else None
    )
    instrument_id = _safe_identifier(survey_title or "limesurvey_import", "limesurvey_import")
    try:
        return QuestionnaireParent(
            instrument_id=instrument_id,
            name_full=survey_title or "Imported LimeSurvey Instrument",
            is_commercial=None,
            metadata=QuestionnaireMetadata(notes=family_notes),
            versions=[
                QuestionnaireVersion(
                    version_id="limesurvey_import_v1",
                    language=language,
                    display_name="Imported from LimeSurvey TSV",
                    response_sets={
                        name: options for name, options in response_sets.items() if options
                    },
                    items=resolved_items,
                )
            ],
        )
    except ValidationError as error:
        raise LimeSurveyImportError(
            "LimeSurvey content did not meet PsyMetriQ schema requirements "
            f"({type(error).__name__})"
        ) from None
