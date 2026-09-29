"""Live REDCap project connection: push/pull a questionnaire's Data Dictionary.

This module never grants or infers redistribution rights -- it only moves
already-validated PsyMetriQ questionnaire data to/from a REDCap project the
caller already holds an API token for, exactly as the file-based Data
Dictionary CSV export/import in ``src/exporters/data_exchange.py`` does, just
without a manual download/upload step.

REDCap's Metadata Import API call (``import_metadata``) replaces a project's
ENTIRE data dictionary, not just the fields being sent. Pushing a
questionnaire therefore always reads the project's current metadata first,
refuses outright if any new field name would collide with an existing one
(case-insensitively), and only ever imports (existing fields + new fields)
merged together. It never silently drops, renames, or overwrites an existing
field in someone's REDCap project.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import redcap

from schemas.questionnaire_schema import QuestionnaireParent, QuestionnaireVersion
from src.exporters.data_exchange import (
    REDCAP_HEADER_TO_KEY,
    DataExchangeError,
    build_redcap_metadata_records,
    import_redcap_data_dictionary,
)

LOGGER = logging.getLogger(__name__)


class RedcapApiError(RuntimeError):
    """Raised when a REDCap project cannot be reached, authenticated, or safely updated."""


class RedcapProjectProtocol(Protocol):
    """The subset of ``redcap.Project`` this module relies on."""

    def export_project_info(self, format_type: str = "json") -> Any: ...

    def export_metadata(self, format_type: str = "json") -> Any: ...

    def import_metadata(self, to_import: Any, import_format: str = "json") -> Any: ...


@dataclass(frozen=True)
class RedcapProjectSummary:
    """A human-checkable identity for a connected REDCap project."""

    project_id: str
    project_title: str
    is_longitudinal: bool


@dataclass(frozen=True)
class RedcapPushResult:
    """What actually happened during one metadata push."""

    form_name: str
    pushed_field_count: int
    total_field_count: int
    updated_field_count: int = 0


def connect(url: str, token: str) -> redcap.Project:
    """Open a REDCap project connection, wrapping auth/network failures clearly.

    The token is used only for this connection; it is never logged and the
    caller is responsible for keeping it out of settings/project files (see
    ``docs/security.md``).
    """
    if not url.strip() or not token.strip():
        raise RedcapApiError("REDCap API URL and token are required")
    try:
        return redcap.Project(url.strip(), token.strip())
    except Exception as error:
        LOGGER.warning("Could not connect to REDCap project (%s)", type(error).__name__)
        raise RedcapApiError(
            "Could not connect to the REDCap project; check the API URL and token"
        ) from None


def describe_project(project: RedcapProjectProtocol) -> RedcapProjectSummary:
    """Confirm a live connection and return a human-checkable project identity."""
    try:
        info = project.export_project_info(format_type="json")
    except Exception as error:
        LOGGER.warning("Could not read REDCap project info (%s)", type(error).__name__)
        raise RedcapApiError("Could not read the REDCap project's information") from None
    if not isinstance(info, dict):
        raise RedcapApiError("REDCap returned an unexpected project-info response")
    return RedcapProjectSummary(
        project_id=str(info.get("project_id", "")),
        project_title=str(info.get("project_title") or "Unbenanntes REDCap-Projekt"),
        is_longitudinal=bool(info.get("is_longitudinal")),
    )


def push_questionnaire_to_project(
    project: RedcapProjectProtocol,
    questionnaire: QuestionnaireParent,
    version: QuestionnaireVersion,
    *,
    allow_update: bool = False,
) -> RedcapPushResult:
    """Merge one version's fields into the project's data dictionary and push it.

    Always fetches the current metadata first and checks every new field name
    against it case-insensitively. By default (``allow_update=False``) any
    collision refuses the whole push, raising ``RedcapApiError``, so a first
    push can only ever add fields. Passing ``allow_update=True`` is an
    explicit, opt-in way to instead replace exactly the colliding fields'
    definitions with the newly built ones -- for example to correct or
    re-export an instrument you already pushed -- while every other existing
    field (including ones from other instruments/forms) is left untouched
    and kept in its original position.
    """
    new_records = build_redcap_metadata_records(questionnaire, version)
    if not new_records:
        raise RedcapApiError("This version has no exportable fields")
    form_name = str(new_records[0]["form_name"])

    try:
        existing_records = project.export_metadata(format_type="json")
    except Exception as error:
        LOGGER.warning("Could not read existing REDCap metadata (%s)", type(error).__name__)
        raise RedcapApiError("Could not read the project's existing data dictionary") from None
    if not isinstance(existing_records, list):
        raise RedcapApiError("REDCap returned an unexpected metadata response")

    existing_names = {
        str(record.get("field_name", "")).casefold()
        for record in existing_records
        if isinstance(record, dict)
    }
    new_names = [str(record["field_name"]) for record in new_records]
    collisions = sorted({name for name in new_names if name.casefold() in existing_names})
    if collisions and not allow_update:
        raise RedcapApiError(
            "Refusing to push: these field names already exist in the REDCap project "
            "and a metadata push would replace the whole data dictionary, so it would "
            f"overwrite them: {', '.join(collisions)}. Pass allow_update=True to "
            "deliberately replace exactly these fields."
        )

    new_by_name = {str(record["field_name"]).casefold(): record for record in new_records}
    merged_records: list[dict[str, Any]] = []
    replaced_names: set[str] = set()
    for record in existing_records:
        name = str(record.get("field_name", "")).casefold() if isinstance(record, dict) else None
        if name is not None and name in new_by_name:
            merged_records.append(new_by_name[name])
            replaced_names.add(name)
        else:
            merged_records.append(record)
    for record in new_records:
        if str(record["field_name"]).casefold() not in replaced_names:
            merged_records.append(record)

    try:
        project.import_metadata(merged_records, import_format="json")
    except Exception as error:
        LOGGER.warning("Could not push REDCap metadata (%s)", type(error).__name__)
        raise RedcapApiError(
            "REDCap rejected the data dictionary; check field names/choices for validity"
        ) from None

    return RedcapPushResult(
        form_name=form_name,
        pushed_field_count=len(new_records),
        total_field_count=len(merged_records),
        updated_field_count=len(replaced_names),
    )


def _metadata_records_to_csv(records: list[dict[str, Any]]) -> str:
    """Reshape REDCap API metadata JSON records into Data Dictionary CSV text."""
    output = io.StringIO(newline="")
    headers = list(REDCAP_HEADER_TO_KEY)
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for record in records:
        if not isinstance(record, dict):
            continue
        writer.writerow(
            {header: record.get(key, "") for header, key in REDCAP_HEADER_TO_KEY.items()}
        )
    return output.getvalue()


def pull_questionnaire_from_project(
    project: RedcapProjectProtocol, *, language: str = "en"
) -> QuestionnaireParent:
    """Read a REDCap project's entire data dictionary as a PsyMetriQ questionnaire.

    Reuses ``import_redcap_data_dictionary`` (the same parser used for a
    manually exported/uploaded Data Dictionary CSV), so a live pull and a
    file upload behave identically -- including which field types are
    imported as items and which are only noted as skipped.
    """
    try:
        records = project.export_metadata(format_type="json")
    except Exception as error:
        LOGGER.warning("Could not read REDCap metadata (%s)", type(error).__name__)
        raise RedcapApiError("Could not read the project's data dictionary") from None
    if not isinstance(records, list) or not records:
        raise RedcapApiError("The REDCap project has no data dictionary to import")

    csv_text = _metadata_records_to_csv(records)
    try:
        return import_redcap_data_dictionary(csv_text, language=language)
    except DataExchangeError as error:
        raise RedcapApiError(str(error)) from None
