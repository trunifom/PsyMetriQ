"""Best-effort Unipark/EFS Survey "Paste from Word" question-text export/import.

Unipark (EFS Survey / Tivian Discover XI) does not publish its internal
project export format (``.gpx``) at all: it is closed-source, and Tivian's
own support portal does not document that XML schema anywhere searchable.
Generating or parsing ``.gpx`` would therefore be pure guessing with no way
to verify correctness -- unlike this project's REDCap support (checked
against PyCap's real API) and LimeSurvey support (checked against
LimeSurvey's own open-source importer code). This module deliberately does
not attempt it.

Instead, this targets the one Unipark import mechanism Tivian's own support
documentation describes with a concrete, quotable example: "Paste from
Word" (https://support.tivian.com/article/49018-questionnaire, fetched
2026-09-29), which creates several questions at once from plain structured
text pasted into the questionnaire editor. Per that documentation: each
question is one text block, separated by a blank line; a question's answer
options each occupy one line, optionally with an explicit numeric code
using a semicolon separator (documented example: ``1;Software``); a
question with no following answer-option lines becomes a free-text
question.

This does **not** cover matrix/scale questions, Unipark's internal numeric
question-type codes (its own docs show these, e.g. "Question text - 311",
without explaining what determines them), or branching/filter logic --
none of these are documented in enough concrete, verifiable detail to
implement with confidence, and Tivian's own docs state the paste feature
"cannot be used for all question types" without listing which. The output
is plain text meant to be pasted into Unipark's "Paste from Word" dialog,
not a file Unipark opens directly. Check the pasted result in Unipark's own
editor before relying on it for a real study.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)


class UniparkExportError(RuntimeError):
    """Raised when a questionnaire version cannot be rendered as Unipark paste text."""


class UniparkImportError(RuntimeError):
    """Raised when pasted Unipark question text is malformed or has no questions."""


def _safe_identifier(value: str, fallback: str, *, max_length: int = 40) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    if not normalized or not normalized[0].isalpha():
        normalized = f"{fallback}_{normalized}" if normalized else fallback
    return normalized[:max_length].rstrip("_") or fallback


def _safe_variable_name(value: str, index: int, *, max_length: int = 20) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"q_{normalized}" if normalized else f"q{index:03d}"
    return normalized[:max_length].rstrip("_") or f"q{index:03d}"


def _unipark_answer_line(option: ResponseOption) -> str:
    """Render one answer option as Unipark's documented ``code;label`` line.

    The semicolon-code syntax only covers integer codes; a non-integer code
    (e.g. a letter code) is rendered as a plain label line instead, and
    Unipark will auto-number it -- this matches the documented behavior for
    a line with no explicit code.
    """
    try:
        code_int = int(option.code)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return option.label
    return f"{code_int};{option.label}"


def export_unipark_text(questionnaire: QuestionnaireParent, version: QuestionnaireVersion) -> str:
    """Render one questionnaire version as Unipark "Paste from Word" question text."""
    if not version.items:
        raise UniparkExportError("This version has no items to export")
    blocks: list[str] = []
    for item in version.items:
        lines = [item.prompt_text]
        if item.response_mode == "categorical" and item.response_set_ref:
            options = version.response_sets.get(item.response_set_ref, [])
            lines.extend(_unipark_answer_line(option) for option in options)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def import_unipark_text(
    content: str, *, language: str = "en", instrument_id: str = "unipark_import"
) -> QuestionnaireParent:
    """Parse pasted Unipark question text back into a PsyMetriQ questionnaire.

    A block with only a question-text line becomes a free-text item; a
    block with following answer-option lines becomes a categorical item. A
    ``code;label`` line uses the given integer code; a plain line is
    auto-numbered starting at 1, matching Unipark's own documented
    behavior for lines with no explicit code.
    """
    blocks = [block for block in re.split(r"\n\s*\n", content.strip()) if block.strip()]
    if not blocks:
        raise UniparkImportError("No question blocks found in the pasted text")

    items: list[ItemSchema] = []
    response_sets: dict[str, list[ResponseOption]] = {}
    used_variable_names: set[str] = set()
    used_item_ids: set[str] = set()
    for index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        prompt = lines[0]
        answer_lines = lines[1:]

        item_id = _safe_identifier(prompt or f"item_{index:03d}", "item")
        if item_id in used_item_ids:
            suffix = f"_{index}"
            item_id = item_id[: max(1, 40 - len(suffix))].rstrip("_") + suffix
        used_item_ids.add(item_id)
        variable_name = _safe_variable_name(prompt or f"q{index}", index)
        if variable_name.casefold() in used_variable_names:
            suffix = f"_{index}"
            variable_name = variable_name[: max(1, 20 - len(suffix))].rstrip("_") + suffix
        used_variable_names.add(variable_name.casefold())

        response_ref: str | None = None
        if answer_lines:
            options: list[ResponseOption] = []
            for option_index, raw_line in enumerate(answer_lines, start=1):
                code_part, separator, label_part = raw_line.partition(";")
                if separator and code_part.strip().lstrip("-").isdigit():
                    code: str | int = int(code_part.strip())
                    label = label_part.strip() or code_part.strip()
                else:
                    code = option_index
                    label = raw_line
                options.append(ResponseOption(code=code, label=label, score=None))
            response_ref = f"unipark_scale_{index:03d}"
            response_sets[response_ref] = options

        items.append(
            ItemSchema(
                item_id=item_id,
                variable_name=variable_name,
                dimension="general",
                prompt_text=prompt,
                response_mode="categorical" if response_ref else "text",
                response_set_ref=response_ref,
            )
        )

    if not items:
        raise UniparkImportError("No importable questions found in the pasted text")

    try:
        return QuestionnaireParent(
            instrument_id=_safe_identifier(instrument_id, "unipark_import"),
            name_full="Imported Unipark Questionnaire",
            is_commercial=None,
            versions=[
                QuestionnaireVersion(
                    version_id="unipark_import_v1",
                    language=language,
                    display_name="Imported from Unipark paste text",
                    response_sets=response_sets,
                    items=items,
                )
            ],
        )
    except ValidationError as error:
        raise UniparkImportError(
            f"Pasted content did not meet PsyMetriQ schema requirements ({type(error).__name__})"
        ) from None
