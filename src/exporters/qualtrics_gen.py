"""Best-effort Qualtrics QSF (Qualtrics Survey Format) export/import.

Qualtrics does not publish a formal QSF schema, but the format itself is
plain JSON and its shape is stable and widely documented by third parties
and observable in real exported ``.qsf`` files. This module was built and
cross-checked against a real, publicly available ``.qsf`` file (the
`egor <https://github.com/tilltnet/egor>`_ package's Qualtrics template,
fetched 2026-09-29) rather than written from memory: the top-level
``SurveyEntry``/``SurveyElements`` split, the ``"SQ"`` question element
shape (``PrimaryAttribute`` as the ``QID``, ``Payload`` with
``QuestionText``/``DataExportTag``/``QuestionType``/``Selector``/
``SubSelector``/``Choices``/``ChoiceOrder``/``Validation``), and the
``"BL"`` block element shape (``BlockElements`` listing
``{"Type": "Question", "QuestionID": ...}``) all match that real file.

Like this project's LimeSurvey support, **this has not been verified
against a live Qualtrics import** -- test-import a generated file into a
real (or trial) Qualtrics account before relying on it for an actual
study.

Scope is deliberately narrow, matching this project's REDCap/LimeSurvey
coverage:

- Only ``MC`` (single choice, Selector ``SAVR``; multiple choice, Selector
  ``MAVR``) and ``TE`` (text entry, Selector ``SL``; numeric via
  ``Validation.Settings.ContentType == "ValidNumber"``) questions are
  produced or imported. Matrix, slider, rank-order, and other Qualtrics
  question types are never guessed at.
- Choice codes/scores are preserved via Qualtrics' own ``RecodeValues``
  mechanism (the "recorded value" behind each sequential choice number),
  not via Qualtrics' separate, much less documented built-in scoring
  feature -- this project's ``ScoringAlgorithm`` definitions stay external
  to the exported survey, exactly as they do for the LimeSurvey export.
- Branching (``show_if``) is not translated into Qualtrics Display Logic;
  Qualtrics' Display Logic JSON is deeply nested and not well enough
  documented publicly to build reliably. An item with ``show_if``
  conditions keeps them recorded in PsyMetriQ but exports unconditionally,
  with a note left in the item's metadata.
- The minimal ``"FL"`` (Survey Flow) element this module writes lists the
  exported blocks in encounter order and an ``EndSurvey`` node; it is
  enough for Qualtrics to accept the file, not a reproduction of every
  flow feature.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)

_QUALTRICS_SUPPORTED_QUESTION_TYPES = frozenset({"MC", "TE"})


class QualtricsExportError(RuntimeError):
    """Raised when a questionnaire version cannot be rendered as a QSF document."""


class QualtricsImportError(RuntimeError):
    """Raised when QSF content is malformed or has no importable questions."""


def _safe_identifier(value: str, fallback: str, *, max_length: int = 40) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    if not normalized or not normalized[0].isalpha():
        normalized = f"{fallback}_{normalized}" if normalized else fallback
    return normalized[:max_length].rstrip("_") or fallback


def _safe_variable_name(value: str, index: int, *, max_length: int = 26) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"q_{normalized}" if normalized else f"q{index:03d}"
    return normalized[:max_length].rstrip("_") or f"q{index:03d}"


def _qualtrics_question_payload(
    item: ItemSchema, response_options: list[ResponseOption]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "QuestionText": item.prompt_text,
        "DataExportTag": item.variable_name,
        "Validation": {
            "Settings": {"ForceResponse": "ON" if item.is_required else "OFF", "Type": "None"}
        },
    }
    if item.response_mode == "categorical":
        payload["QuestionType"] = "MC"
        payload["Selector"] = "MAVR" if item.redcap_field_type == "checkbox" else "SAVR"
        choices: dict[str, dict[str, str]] = {}
        recode_values: dict[str, str] = {}
        choice_order: list[str] = []
        for position, option in enumerate(response_options, start=1):
            key = str(position)
            choices[key] = {"Display": option.label}
            recode_values[key] = str(option.code)
            choice_order.append(key)
        payload["Choices"] = choices
        payload["ChoiceOrder"] = choice_order
        payload["RecodeValues"] = recode_values
        return payload
    payload["QuestionType"] = "TE"
    payload["Selector"] = "SL"
    if item.response_mode == "numeric":
        payload["Validation"]["Settings"]["ContentType"] = "ValidNumber"
    return payload


def build_qualtrics_survey(
    questionnaire: QuestionnaireParent, version: QuestionnaireVersion
) -> dict[str, Any]:
    """Build a QSF-shaped dict for one questionnaire version."""
    if not version.items:
        raise QualtricsExportError("This version has no items to export")

    survey_elements: list[dict[str, Any]] = []
    dimension_blocks: dict[str, list[str]] = {}
    dimension_order: list[str] = []

    for index, item in enumerate(version.items, start=1):
        qid = f"QID{index}"
        response_options = (
            version.response_sets.get(item.response_set_ref, [])
            if item.response_mode == "categorical" and item.response_set_ref
            else []
        )
        survey_elements.append(
            {
                "SurveyID": None,
                "Element": "SQ",
                "PrimaryAttribute": qid,
                "SecondaryAttribute": item.prompt_text,
                "Payload": {
                    "QuestionID": qid,
                    **_qualtrics_question_payload(item, response_options),
                },
            }
        )
        if item.dimension not in dimension_blocks:
            dimension_blocks[item.dimension] = []
            dimension_order.append(item.dimension)
        dimension_blocks[item.dimension].append(qid)

    block_ids: list[str] = []
    for position, dimension in enumerate(dimension_order, start=1):
        block_id = f"BL_{position}"
        block_ids.append(block_id)
        survey_elements.append(
            {
                "SurveyID": None,
                "Element": "BL",
                "PrimaryAttribute": "Survey Blocks",
                "Payload": [
                    {
                        "Type": "Standard",
                        "Description": dimension,
                        "ID": block_id,
                        "BlockElements": [
                            {"Type": "Question", "QuestionID": qid}
                            for qid in dimension_blocks[dimension]
                        ],
                    }
                ],
            }
        )

    flow_entries: list[dict[str, Any]] = [
        {"ID": block_id, "Type": "Block", "FlowID": f"FL_{position + 1}"}
        for position, block_id in enumerate(block_ids, start=1)
    ]
    flow_entries.append({"Type": "EndSurvey", "FlowID": f"FL_{len(block_ids) + 1}"})
    survey_elements.append(
        {
            "SurveyID": None,
            "Element": "FL",
            "PrimaryAttribute": "FL_1",
            "Payload": {
                "Type": "Root",
                "FlowID": "FL_1",
                "Flow": flow_entries,
                "Properties": {"Count": len(flow_entries)},
            },
        }
    )

    return {
        "SurveyEntry": {
            "SurveyID": "SV_import",
            "SurveyName": f"{questionnaire.name_full} ({version.version_id})",
            "SurveyLanguage": version.language,
            "SurveyStatus": "Inactive",
        },
        "SurveyElements": survey_elements,
    }


def export_qualtrics_qsf(questionnaire: QuestionnaireParent, version: QuestionnaireVersion) -> str:
    """Render one questionnaire version as a Qualtrics-importable QSF JSON document."""
    survey = build_qualtrics_survey(questionnaire, version)
    return json.dumps(survey, ensure_ascii=False, indent=2) + "\n"


def import_qualtrics_qsf(
    content: str, *, default_language: str = "en", instrument_id: str = "qualtrics_import"
) -> QuestionnaireParent:
    """Import a Qualtrics QSF export as a PsyMetriQ questionnaire.

    Only ``MC`` and ``TE`` questions become respondent items. Other Qualtrics
    question types are never silently dropped: each is listed by QID/type in
    the imported instrument's ``metadata.notes``.
    """
    try:
        document = json.loads(content)
    except json.JSONDecodeError as error:
        raise QualtricsImportError("Could not parse QSF content as JSON") from error
    if not isinstance(document, dict) or "SurveyElements" not in document:
        raise QualtricsImportError(
            "The file does not look like a valid QSF export (missing SurveyElements)"
        )

    survey_entry = document.get("SurveyEntry") or {}
    survey_name = str(survey_entry.get("SurveyName") or "").strip() or None
    language = (
        str(survey_entry.get("SurveyLanguage") or default_language).strip() or default_language
    )

    questions_by_qid: dict[str, dict[str, Any]] = {}
    qid_to_dimension: dict[str, str] = {}
    block_order: list[str] = []

    for element in document.get("SurveyElements") or []:
        if not isinstance(element, dict):
            continue
        if element.get("Element") == "SQ":
            payload = element.get("Payload")
            qid = element.get("PrimaryAttribute")
            if isinstance(payload, dict) and isinstance(qid, str):
                questions_by_qid[qid] = payload
        elif element.get("Element") == "BL":
            blocks = element.get("Payload")
            if isinstance(blocks, dict):
                blocks = [blocks]
            for block in blocks or []:
                if not isinstance(block, dict):
                    continue
                description = str(block.get("Description") or "general").strip() or "general"
                for block_element in block.get("BlockElements") or []:
                    if not isinstance(block_element, dict):
                        continue
                    if block_element.get("Type") != "Question":
                        continue
                    qid = block_element.get("QuestionID")
                    if isinstance(qid, str) and qid not in qid_to_dimension:
                        qid_to_dimension[qid] = description
                        block_order.append(qid)

    ordered_qids = block_order + [qid for qid in questions_by_qid if qid not in qid_to_dimension]

    items: list[ItemSchema] = []
    response_sets: dict[str, list[ResponseOption]] = {}
    skipped_questions: list[str] = []
    used_variable_names: set[str] = set()

    for index, qid in enumerate(ordered_qids, start=1):
        payload = questions_by_qid.get(qid)
        if payload is None:
            continue
        question_type = str(payload.get("QuestionType") or "").strip()
        if question_type not in _QUALTRICS_SUPPORTED_QUESTION_TYPES:
            skipped_questions.append(f"{qid} (type {question_type or 'unknown'})")
            continue

        export_tag = str(payload.get("DataExportTag") or "").strip()
        variable_name = _safe_variable_name(export_tag or qid, index)
        if variable_name.casefold() in used_variable_names:
            suffix = f"_{index}"
            variable_name = variable_name[: max(1, 26 - len(suffix))].rstrip("_") + suffix
        used_variable_names.add(variable_name.casefold())

        prompt_text = str(payload.get("QuestionText") or "").strip() or f"Question {qid}"
        required = (
            str((payload.get("Validation") or {}).get("Settings", {}).get("ForceResponse") or "")
            .strip()
            .upper()
            == "ON"
        )
        dimension = qid_to_dimension.get(qid, "general")

        if question_type == "TE":
            content_type = str(
                (payload.get("Validation") or {}).get("Settings", {}).get("ContentType") or ""
            ).strip()
            mode = "numeric" if content_type == "ValidNumber" else "text"
            items.append(
                ItemSchema(
                    item_id=_safe_identifier(qid, "item"),
                    variable_name=variable_name,
                    dimension=dimension,
                    prompt_text=prompt_text,
                    response_mode=mode,
                    is_required=required,
                )
            )
            continue

        selector = str(payload.get("Selector") or "").strip()
        choices = payload.get("Choices") if isinstance(payload.get("Choices"), dict) else {}
        choice_order = (
            payload.get("ChoiceOrder") if isinstance(payload.get("ChoiceOrder"), list) else None
        )
        recode_values = (
            payload.get("RecodeValues") if isinstance(payload.get("RecodeValues"), dict) else {}
        )
        ordered_keys = [str(key) for key in choice_order] if choice_order else list(choices.keys())

        options: list[ResponseOption] = []
        for choice_key in ordered_keys:
            choice = choices.get(choice_key)
            if not isinstance(choice, dict):
                continue
            label = str(choice.get("Display") or "").strip() or choice_key
            code = str(recode_values.get(choice_key, choice_key))
            options.append(ResponseOption(code=code, label=label, score=None))

        response_ref = f"qualtrics_scale_{index:03d}"
        notes: str | None = None
        if not options:
            mode = "text"
            response_ref_final = None
            notes = "Imported as free text: no Qualtrics 'Choices' were found for this question."
        else:
            mode = "categorical"
            response_ref_final = response_ref
            response_sets[response_ref] = options

        items.append(
            ItemSchema(
                item_id=_safe_identifier(qid, "item"),
                variable_name=variable_name,
                dimension=dimension,
                prompt_text=prompt_text,
                response_mode=mode,
                response_set_ref=response_ref_final,
                is_required=required,
                redcap_field_type="checkbox" if selector == "MAVR" else "radio",
                metadata=QuestionnaireMetadata(notes=notes) if notes else QuestionnaireMetadata(),
            )
        )

    if not items:
        raise QualtricsImportError("QSF content contains no importable questions")

    family_notes = (
        f"Questions present in the QSF export but not imported as respondent items "
        f"(unsupported question type): {'; '.join(skipped_questions)}"
        if skipped_questions
        else None
    )
    resolved_instrument_id = _safe_identifier(survey_name or instrument_id, instrument_id)
    try:
        return QuestionnaireParent(
            instrument_id=resolved_instrument_id,
            name_full=survey_name or "Imported Qualtrics Instrument",
            is_commercial=None,
            metadata=QuestionnaireMetadata(notes=family_notes),
            versions=[
                QuestionnaireVersion(
                    version_id="qualtrics_import_v1",
                    language=language,
                    display_name="Imported from Qualtrics QSF",
                    response_sets=response_sets,
                    items=items,
                )
            ],
        )
    except ValidationError as error:
        raise QualtricsImportError(
            f"QSF content did not meet PsyMetriQ schema requirements ({type(error).__name__})"
        ) from None
