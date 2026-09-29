import json
from pathlib import Path
from typing import Any

import pytest

from src.ingestion.zotero_source import (
    ZoteroSourceError,
    ZoteroSyncConfig,
    sync_zotero_library,
)


class FakeZoteroClient:
    """Minimal in-memory stand-in for pyzotero's Zotero client."""

    def __init__(
        self,
        attachments: list[dict[str, Any]],
        parents: dict[str, dict[str, Any]] | None = None,
        files: dict[str, bytes] | None = None,
    ) -> None:
        self._attachments = attachments
        self._parents = parents or {}
        self._files = files or {}
        self.requested_since: int | None = None
        self.collection_requested: str | None = None

    def collection_items(self, collection: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.collection_requested = collection
        self.requested_since = kwargs.get("since")
        return self._attachments

    def items(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.requested_since = kwargs.get("since")
        return self._attachments

    def item(self, item: str, **kwargs: Any) -> dict[str, Any]:
        return self._parents[item]

    def file(self, item: str, **kwargs: Any) -> bytes:
        return self._files[item]


def _attachment(
    key: str, *, version: int, content_type: str = "application/pdf", parent: str | None = "parent1"
) -> dict[str, Any]:
    return {
        "key": key,
        "data": {
            "key": key,
            "itemType": "attachment",
            "contentType": content_type,
            "filename": f"{key}.pdf",
            "version": version,
            "parentItem": parent,
            "title": f"Attachment {key}",
        },
    }


def _parent(key: str, title: str = "Example Instrument Validation Study") -> dict[str, Any]:
    return {
        "data": {
            "key": key,
            "title": title,
            "date": "2020-05-01",
            "DOI": "10.1000/example",
            "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
            "tags": [{"tag": "questionnaire"}],
        }
    }


def _config(tmp_path: Path, collection_key: str | None = None) -> ZoteroSyncConfig:
    return ZoteroSyncConfig(
        library_id="12345",
        library_type="user",
        api_key="fake-key",
        collection_key=collection_key,
        inbox_directory=tmp_path / "inbox",
        state_path=tmp_path / "state.json",
    )


def test_downloads_new_pdf_attachment_and_writes_metadata_note(tmp_path: Path) -> None:
    client = FakeZoteroClient(
        attachments=[_attachment("att1", version=5)],
        parents={"parent1": _parent("parent1")},
        files={"att1": b"%PDF-1.4 fake pdf bytes"},
    )
    config = _config(tmp_path)

    result = sync_zotero_library(config, client=client)

    assert len(result.downloaded) == 1
    pdf_path = config.inbox_directory / result.downloaded[0]
    assert pdf_path.is_file()
    assert pdf_path.read_bytes() == b"%PDF-1.4 fake pdf bytes"

    note_path = pdf_path.with_suffix(pdf_path.suffix + ".zotero-metadata.json")
    note = json.loads(note_path.read_text(encoding="utf-8"))
    assert note["parent_title"] == "Example Instrument Validation Study"
    assert note["authors"] == ["Ada Lovelace"]
    assert note["doi"] == "10.1000/example"
    assert "does not" in note["note"]

    # No rights sidecar is ever created automatically.
    assert not pdf_path.with_suffix(pdf_path.suffix + ".source.json").exists()


def test_skips_non_pdf_attachments(tmp_path: Path) -> None:
    client = FakeZoteroClient(
        attachments=[_attachment("att-note", version=1, content_type="text/html")]
    )
    config = _config(tmp_path)

    result = sync_zotero_library(config, client=client)

    assert result.downloaded == []
    assert result.skipped_non_pdf == 1
    assert list(config.inbox_directory.glob("*.pdf")) == []


def test_repeat_sync_skips_unchanged_attachment_version(tmp_path: Path) -> None:
    client = FakeZoteroClient(
        attachments=[_attachment("att1", version=5)],
        parents={"parent1": _parent("parent1")},
        files={"att1": b"same bytes"},
    )
    config = _config(tmp_path)

    first = sync_zotero_library(config, client=client)
    assert len(first.downloaded) == 1

    second_client = FakeZoteroClient(
        attachments=[_attachment("att1", version=5)],
        parents={"parent1": _parent("parent1")},
        files={"att1": b"same bytes"},
    )
    second = sync_zotero_library(config, client=second_client)

    assert second.downloaded == []
    assert second.skipped_up_to_date == 1


def test_redownloads_when_attachment_version_increases(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first_client = FakeZoteroClient(
        attachments=[_attachment("att1", version=5)],
        parents={"parent1": _parent("parent1")},
        files={"att1": b"version five"},
    )
    sync_zotero_library(config, client=first_client)

    second_client = FakeZoteroClient(
        attachments=[_attachment("att1", version=6)],
        parents={"parent1": _parent("parent1")},
        files={"att1": b"version six"},
    )
    result = sync_zotero_library(config, client=second_client)

    assert len(result.downloaded) == 1
    pdf_path = config.inbox_directory / result.downloaded[0]
    assert pdf_path.read_bytes() == b"version six"


def test_sync_scoped_to_configured_collection(tmp_path: Path) -> None:
    client = FakeZoteroClient(
        attachments=[_attachment("att1", version=1)],
        parents={"parent1": _parent("parent1")},
        files={"att1": b"pdf bytes"},
    )
    config = _config(tmp_path, collection_key="ABCDEFGH")

    sync_zotero_library(config, client=client)

    assert client.collection_requested == "ABCDEFGH"


def test_failed_download_is_reported_without_raising(tmp_path: Path) -> None:
    client = FakeZoteroClient(
        attachments=[_attachment("att1", version=1)],
        parents={"parent1": _parent("parent1")},
        files={},  # .file() will raise KeyError, simulating a download failure
    )
    config = _config(tmp_path)

    result = sync_zotero_library(config, client=client)

    assert result.downloaded == []
    assert result.failed == ["att1"]


def test_invalid_library_type_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ZoteroSourceError):
        ZoteroSyncConfig(
            library_id="1",
            library_type="organization",
            api_key="key",
            inbox_directory=tmp_path / "inbox",
            state_path=tmp_path / "state.json",
        )
