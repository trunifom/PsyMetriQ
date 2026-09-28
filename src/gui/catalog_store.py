"""Validated local catalogue access and conflict-safe questionnaire imports."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path

from pydantic import ValidationError

from schemas.questionnaire_schema import QuestionnaireParent

LOGGER = logging.getLogger(__name__)


class CatalogStoreError(RuntimeError):
    """Raised when a catalogue cannot be validated or safely updated."""


class QuestionnaireCatalogStore:
    """Read and update a folder of canonical PsyMetriQ JSON families."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def load(self) -> list[tuple[QuestionnaireParent, Path]]:
        """Validate every catalogue file before returning a new in-memory snapshot."""
        try:
            paths = sorted(self.directory.glob("*.json"))
        except OSError as error:
            raise CatalogStoreError("Could not list the catalogue directory") from error

        records: list[tuple[QuestionnaireParent, Path]] = []
        seen_ids: set[str] = set()
        for path in paths:
            try:
                questionnaire = QuestionnaireParent.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError) as error:
                LOGGER.error(
                    "Could not validate catalogue file %s (%s)",
                    path.name,
                    type(error).__name__,
                )
                raise CatalogStoreError(
                    f"Catalogue file {path.name} is invalid; current view was not replaced"
                ) from None
            if questionnaire.instrument_id in seen_ids:
                raise CatalogStoreError(
                    f"Duplicate instrument ID {questionnaire.instrument_id!r} in catalogue"
                )
            seen_ids.add(questionnaire.instrument_id)
            records.append((questionnaire, path))
        return records

    def import_families(
        self, imported: list[QuestionnaireParent]
    ) -> list[QuestionnaireParent]:
        """Merge new versions by stable instrument ID and refuse silent replacement."""
        if not imported:
            return []
        self.directory.mkdir(parents=True, exist_ok=True)
        existing_records = self.load()
        existing_by_id = {
            questionnaire.instrument_id: (questionnaire, path)
            for questionnaire, path in existing_records
        }
        prepared: list[tuple[QuestionnaireParent, Path]] = []
        imported_ids: set[str] = set()

        for candidate in imported:
            if candidate.instrument_id in imported_ids:
                raise CatalogStoreError(
                    f"Import contains duplicate instrument ID {candidate.instrument_id!r}"
                )
            imported_ids.add(candidate.instrument_id)
            existing_record = existing_by_id.get(candidate.instrument_id)
            if existing_record is not None:
                existing, target_path = existing_record
                merged = self._merge_versions(existing, candidate)
            else:
                merged = candidate
                target_path = self._target_path(candidate.instrument_id)
                if target_path.exists():
                    try:
                        target_owner = QuestionnaireParent.model_validate_json(
                            target_path.read_text(encoding="utf-8")
                        )
                    except (OSError, UnicodeError, ValidationError):
                        raise CatalogStoreError(
                            f"Target file {target_path.name} exists and is not a valid "
                            "catalogue family"
                        ) from None
                    if target_owner.instrument_id != candidate.instrument_id:
                        raise CatalogStoreError(
                            f"Target filename {target_path.name} conflicts with another instrument"
                        )
                    existing_by_id[candidate.instrument_id] = (target_owner, target_path)
                    merged = self._merge_versions(target_owner, candidate)
            prepared.append((merged, target_path))

        for questionnaire, target_path in prepared:
            self._write_json(target_path, questionnaire.model_dump(mode="json"))
        return [questionnaire for questionnaire, _path in prepared]

    @staticmethod
    def _merge_versions(
        existing: QuestionnaireParent, candidate: QuestionnaireParent
    ) -> QuestionnaireParent:
        if existing.is_commercial != candidate.is_commercial:
            raise CatalogStoreError(
                f"Commercial-use metadata conflicts for {candidate.instrument_id!r}"
            )
        existing_version_ids = {version.version_id for version in existing.versions}
        candidate_version_ids = {version.version_id for version in candidate.versions}
        if existing_version_ids & candidate_version_ids:
            raise CatalogStoreError(
                f"Version conflict for {candidate.instrument_id!r}; no version was replaced"
            )
        try:
            return QuestionnaireParent.model_validate(
                existing.model_copy(
                    update={"versions": [*existing.versions, *candidate.versions]}
                ).model_dump(mode="json")
            )
        except ValidationError as error:
            raise CatalogStoreError(
                f"Imported versions do not validate for {candidate.instrument_id!r} "
                f"({type(error).__name__})"
            ) from None

    def _target_path(self, instrument_id: str) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", instrument_id).strip("_-")
        if not safe_name:
            raise CatalogStoreError("Instrument ID cannot be represented as a safe filename")
        return self.directory / f"{safe_name[:100]}.json"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            LOGGER.error("Could not write catalogue file %s (%s)", path.name, type(error).__name__)
            raise CatalogStoreError(f"Could not save catalogue file {path.name}") from None
