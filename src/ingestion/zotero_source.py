"""Pull PDF attachments from a Zotero library into the local questionnaire inbox.

This module only stages files for the existing rights-gated intake pipeline in
``src/ingestion/document_pipeline.py``. It never infers redistribution rights
from Zotero metadata, tags, or collection membership: a downloaded PDF still
requires a human-reviewed ``<filename>.pdf.source.json`` sidecar before the
pipeline will publish it. Alongside each PDF this module writes a plain
``<filename>.pdf.zotero-metadata.json`` note (title, authors, DOI, Zotero web
link) purely to speed up writing that rights sidecar by hand.

Sync is incremental: Zotero library versions are tracked in a local state file
so repeated runs only fetch new or changed attachments.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from schemas.questionnaire_schema import QuestionnaireParent, QuestionnaireVersion

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOX = PROJECT_ROOT / "data" / "questionnaires" / "inbox"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "questionnaires" / "review" / "zotero_sync_state.json"

_PDF_CONTENT_TYPE = "application/pdf"


class ZoteroSourceError(RuntimeError):
    """Raised when the configured Zotero library cannot be synced safely."""


class ZoteroClientProtocol(Protocol):
    """The subset of ``pyzotero.zotero.Zotero`` this module relies on."""

    def collection_items(self, collection: str, **kwargs: Any) -> list[dict[str, Any]]: ...

    def items(self, **kwargs: Any) -> list[dict[str, Any]]: ...

    def item(self, item: str, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover - typing only
        ...

    def file(self, item: str, **kwargs: Any) -> bytes: ...

    def last_modified_version(self) -> int: ...

    def item_template(self, itemtype: str) -> dict[str, Any]: ...

    def create_items(self, payload: list[dict[str, Any]]) -> Any: ...

    def attachment_simple(self, files: list[str], parentid: str | None = None) -> Any: ...


class SyncedAttachment(BaseModel):
    """Local record of one already-downloaded attachment version."""

    version: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inbox_filename: str
    synced_at: datetime


class ZoteroSyncState(BaseModel):
    """Persisted local sync progress; never stores rights or approval data."""

    library_version: int = 0
    synced_attachments: dict[str, SyncedAttachment] = Field(default_factory=dict)


class ZoteroAttachmentNote(BaseModel):
    """Human-readable context saved beside a downloaded PDF, not a rights approval."""

    attachment_key: str
    parent_key: str | None = None
    title: str
    parent_title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    zotero_web_url: str
    tags: list[str] = Field(default_factory=list)
    note: str = (
        "This file is Zotero metadata for reviewer convenience only. It does not "
        "grant redistribution rights. Create a matching "
        "<filename>.pdf.source.json rights sidecar before this PDF can be "
        "catalogued."
    )


class ZoteroSyncResult(BaseModel):
    """Summary of one sync pass."""

    downloaded: list[str] = Field(default_factory=list)
    skipped_non_pdf: int = 0
    skipped_up_to_date: int = 0
    failed: list[str] = Field(default_factory=list)


class ZoteroSyncConfig:
    """Filesystem and library-scope settings for one sync run."""

    def __init__(
        self,
        *,
        library_id: str,
        library_type: str = "user",
        api_key: str,
        collection_key: str | None = None,
        inbox_directory: Path = DEFAULT_INBOX,
        state_path: Path = DEFAULT_STATE_PATH,
    ) -> None:
        if library_type not in ("user", "group"):
            raise ZoteroSourceError("library_type must be 'user' or 'group'")
        self.library_id = library_id
        self.library_type = library_type
        self.api_key = api_key
        self.collection_key = collection_key
        self.inbox_directory = inbox_directory
        self.state_path = state_path


class ZoteroPushResult(BaseModel):
    """What was created in Zotero for one exported questionnaire version."""

    item_key: str
    attached_file: str | None = None


def _extract_created_item_key(response: Any) -> str | None:
    """Read the new item's key from either Zotero API response shape."""
    if not isinstance(response, dict):
        return None
    successful = response.get("successful")
    if not isinstance(successful, dict):
        successful = response.get("success")
    if not isinstance(successful, dict) or not successful:
        return None
    first = next(iter(successful.values()))
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        key = first.get("key")
        if key is None and isinstance(first.get("data"), dict):
            key = first["data"].get("key")
        return key
    return None


def push_questionnaire_to_zotero(
    config: ZoteroSyncConfig,
    *,
    questionnaire: QuestionnaireParent,
    version: QuestionnaireVersion,
    export_file_path: Path | None = None,
    client: ZoteroClientProtocol | None = None,
) -> ZoteroPushResult:
    """Create a Zotero reference item for one exported questionnaire version.

    This records that you exported this instrument/version from PsyMetriQ --
    a citation/reference item, not a substitute for the source publication.
    If ``export_file_path`` is given (an already-exported file already on
    disk), it is attached to the new item so the export travels with your
    Zotero library. Nothing about redistribution rights is inferred or
    changed by creating this item or attaching this file; that remains
    governed entirely by the source's own recorded rights sidecar.
    """
    if client is None:
        from pyzotero import zotero as pyzotero_zotero

        client = pyzotero_zotero.Zotero(config.library_id, config.library_type, config.api_key)

    try:
        template = client.item_template("document")
    except Exception as error:
        raise ZoteroSourceError(
            f"Could not fetch a Zotero item template ({type(error).__name__})"
        ) from None

    template["title"] = f"{questionnaire.name_full} ({version.version_id}) -- PsyMetriQ export"
    extra_lines = [
        f"psymetriq_instrument_id: {questionnaire.instrument_id}",
        f"psymetriq_version_id: {version.version_id}",
        f"psymetriq_language: {version.language}",
    ]
    if version.source_citation:
        extra_lines.append(f"source_citation: {version.source_citation}")
    if version.source_doi:
        extra_lines.append(f"source_doi: {version.source_doi}")
    template["extra"] = "\n".join(extra_lines)
    if "abstractNote" in template:
        template["abstractNote"] = (
            f"Exported from PsyMetriQ: instrument {questionnaire.instrument_id!r}, "
            f"version {version.version_id!r}."
        )
    if "tags" in template:
        template["tags"] = [{"tag": "psymetriq-export"}]
    if config.collection_key and "collections" in template:
        template["collections"] = [config.collection_key]

    try:
        response = client.create_items([template])
    except Exception as error:
        raise ZoteroSourceError(
            f"Could not create the Zotero item ({type(error).__name__})"
        ) from None
    item_key = _extract_created_item_key(response)
    if item_key is None:
        raise ZoteroSourceError("Zotero did not report a created item key")

    attached_file: str | None = None
    if export_file_path is not None:
        try:
            client.attachment_simple([str(export_file_path)], item_key)
        except Exception as error:
            LOGGER.warning(
                "Could not attach export file to Zotero item %s (%s)",
                item_key,
                type(error).__name__,
            )
        else:
            attached_file = export_file_path.name

    return ZoteroPushResult(item_key=item_key, attached_file=attached_file)


def _load_state(state_path: Path) -> ZoteroSyncState:
    if not state_path.is_file():
        return ZoteroSyncState()
    try:
        return ZoteroSyncState.model_validate_json(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError):
        LOGGER.warning("Zotero sync state is unreadable; starting a fresh sync")
        return ZoteroSyncState()


def _write_state(state_path: Path, state: ZoteroSyncState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(state_path.suffix + ".tmp")
    try:
        temporary_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary_path, state_path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


def _safe_filename_segment(value: str, fallback: str = "attachment") -> str:
    import re

    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("._-")
    return normalized[:80] or fallback


def _extract_year(date_value: str | None) -> int | None:
    if not date_value:
        return None
    tokens = date_value.replace("-", " ").split()
    match = next((token for token in tokens if token[:4].isdigit()), None)
    if match is None:
        return None
    try:
        return int(match[:4])
    except ValueError:
        return None


def _build_note(
    *,
    attachment: dict[str, Any],
    parent: dict[str, Any] | None,
    library_id: str,
) -> ZoteroAttachmentNote:
    attachment_data = attachment.get("data", {})
    attachment_key = attachment.get("key", attachment_data.get("key", ""))
    parent_data = parent.get("data", {}) if parent else {}
    parent_key = attachment_data.get("parentItem")
    authors: list[str] = []
    for creator in parent_data.get("creators", []):
        if not isinstance(creator, dict):
            continue
        full_name = " ".join(
            filter(None, [creator.get("firstName"), creator.get("lastName")])
        ).strip()
        authors.append(full_name or creator.get("name", ""))
    authors = [name for name in authors if name]
    doi = parent_data.get("DOI") or None
    title = parent_data.get("title") or attachment_data.get("title") or "Untitled Zotero item"
    return ZoteroAttachmentNote(
        attachment_key=attachment_key,
        parent_key=parent_key,
        title=attachment_data.get("title") or title,
        parent_title=parent_data.get("title") if parent else None,
        authors=authors,
        publication_year=_extract_year(parent_data.get("date")),
        doi=doi,
        zotero_web_url=f"https://www.zotero.org/{library_id}/items/{parent_key or attachment_key}",
        tags=[
            tag.get("tag", "")
            for tag in parent_data.get("tags", [])
            if isinstance(tag, dict) and tag.get("tag")
        ],
    )


def sync_zotero_library(
    config: ZoteroSyncConfig,
    *,
    client: ZoteroClientProtocol | None = None,
) -> ZoteroSyncResult:
    """Download new or changed PDF attachments from Zotero into the local inbox.

    Only ``application/pdf`` attachments are staged. Every download is paired
    with an informational metadata note; no rights sidecar is created, so the
    intake pipeline still requires an explicit human rights review before
    publishing anything derived from these files.
    """
    if client is None:
        from pyzotero import zotero as pyzotero_zotero

        client = pyzotero_zotero.Zotero(
            config.library_id, config.library_type, config.api_key
        )

    state = _load_state(config.state_path)
    config.inbox_directory.mkdir(parents=True, exist_ok=True)

    try:
        if config.collection_key:
            items = client.collection_items(
                config.collection_key, itemType="attachment", since=state.library_version
            )
        else:
            items = client.items(itemType="attachment", since=state.library_version)
    except Exception as error:  # pyzotero raises library-specific HTTP errors
        raise ZoteroSourceError(
            f"Could not list Zotero attachments ({type(error).__name__})"
        ) from None

    result = ZoteroSyncResult()
    highest_version_seen = state.library_version
    parent_cache: dict[str, dict[str, Any] | None] = {}

    for attachment in items:
        attachment_data = attachment.get("data", {})
        attachment_key = attachment.get("key") or attachment_data.get("key")
        version = attachment_data.get("version", 0)
        highest_version_seen = max(highest_version_seen, version)
        if not attachment_key:
            continue
        if attachment_data.get("contentType") != _PDF_CONTENT_TYPE:
            result.skipped_non_pdf += 1
            continue

        existing = state.synced_attachments.get(attachment_key)
        if existing is not None and existing.version >= version:
            result.skipped_up_to_date += 1
            continue

        try:
            file_bytes = client.file(attachment_key)
        except Exception as error:
            LOGGER.warning(
                "Could not download Zotero attachment %s (%s)",
                attachment_key,
                type(error).__name__,
            )
            result.failed.append(attachment_key)
            continue

        digest = hashlib.sha256(file_bytes).hexdigest()
        original_name = attachment_data.get("filename") or f"{attachment_key}.pdf"
        key_segment = _safe_filename_segment(attachment_key)
        name_segment = _safe_filename_segment(Path(original_name).stem)
        inbox_filename = f"zotero_{key_segment}_{name_segment}.pdf"
        destination = config.inbox_directory / inbox_filename
        temporary_path = destination.with_suffix(".pdf.tmp")
        try:
            temporary_path.write_bytes(file_bytes)
            os.replace(temporary_path, destination)
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            LOGGER.warning(
                "Could not write Zotero attachment %s to inbox (%s)",
                attachment_key,
                type(error).__name__,
            )
            result.failed.append(attachment_key)
            continue

        parent_key = attachment_data.get("parentItem")
        parent_item: dict[str, Any] | None = None
        if parent_key:
            if parent_key not in parent_cache:
                try:
                    parent_cache[parent_key] = client.item(parent_key)
                except Exception:
                    parent_cache[parent_key] = None
            parent_item = parent_cache[parent_key]

        note = _build_note(attachment=attachment, parent=parent_item, library_id=config.library_id)
        note_path = destination.with_suffix(destination.suffix + ".zotero-metadata.json")
        note_path.write_text(note.model_dump_json(indent=2), encoding="utf-8")

        state.synced_attachments[attachment_key] = SyncedAttachment(
            version=version,
            sha256=digest,
            inbox_filename=inbox_filename,
            synced_at=datetime.now(timezone.utc),
        )
        result.downloaded.append(inbox_filename)

    state.library_version = max(highest_version_seen, state.library_version)
    _write_state(config.state_path, state)
    return result


def main() -> None:
    """Run one Zotero sync pass using credentials from the environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-id", help="Overrides ZOTERO_USER_ID / ZOTERO_LIBRARY_ID.")
    parser.add_argument(
        "--library-type",
        choices=("user", "group"),
        default=None,
        help="Overrides ZOTERO_LIBRARY_TYPE (default: user).",
    )
    parser.add_argument(
        "--collection-key",
        default=None,
        help="Restrict sync to one collection; overrides ZOTERO_COLLECTION_KEY.",
    )
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_PATH)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    library_id = arguments.library_id or os.environ.get("ZOTERO_LIBRARY_ID") or os.environ.get(
        "ZOTERO_USER_ID"
    )
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_type = arguments.library_type or os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
    collection_key = arguments.collection_key or os.environ.get("ZOTERO_COLLECTION_KEY")
    if not library_id or not api_key:
        raise SystemExit(
            "ZOTERO_API_KEY and ZOTERO_USER_ID/ZOTERO_LIBRARY_ID must be set (.env or flags)"
        )

    config = ZoteroSyncConfig(
        library_id=library_id,
        library_type=library_type,
        api_key=api_key,
        collection_key=collection_key,
        inbox_directory=arguments.inbox,
        state_path=arguments.state_file,
    )
    try:
        result = sync_zotero_library(config)
    except ZoteroSourceError:
        LOGGER.exception("Zotero sync could not be completed")
        raise SystemExit(1) from None

    LOGGER.info(
        "Zotero sync: %d downloaded, %d up to date, %d non-PDF skipped, %d failed",
        len(result.downloaded),
        result.skipped_up_to_date,
        result.skipped_non_pdf,
        len(result.failed),
    )
    for filename in result.downloaded:
        LOGGER.info("Staged %s in the inbox; add a matching rights sidecar before intake", filename)


if __name__ == "__main__":
    main()
