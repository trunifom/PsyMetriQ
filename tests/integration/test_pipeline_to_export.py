"""End-to-end integration: PDF intake -> catalogue storage/search -> export.

Unlike the unit tests under tests/unit/, which exercise one module in
isolation with mocked collaborators, these tests drive the real modules
together through one isolated temporary project root: a synthetic PDF with
a matching rights sidecar is ingested by the real
``QuestionnaireDocumentPipeline`` (only the LLM call is replaced by a fixed
extractor, so no network is used), promoted into a real catalogue JSON file
on disk, loaded back through the real ``QuestionnaireCatalogStore`` and
``QuestionnaireSearchEngine``, and exported through every supported
file-based format plus a (fake, in-memory) live REDCap push.

They reuse the PDF/approval/extractor fixtures from
``tests/unit/test_document_pipeline.py`` rather than re-deriving them, so
the two suites cannot silently drift into testing different synthetic data.
"""

import asyncio
from pathlib import Path
from typing import Any

from src.core.search_engine import QuestionnaireSearchEngine
from src.exporters.data_exchange import (
    export_fhir_questionnaire,
    export_item_csv,
    export_psymetriq_json,
    export_questionnaire_xlsx,
    export_redcap_data_dictionary,
    import_fhir_questionnaire,
    import_psymetriq_json,
    import_redcap_data_dictionary,
)
from src.exporters.redcap_api import push_questionnaire_to_project
from src.gui.catalog_store import QuestionnaireCatalogStore
from src.ingestion.document_pipeline import QuestionnaireDocumentPipeline
from tests.unit.test_document_pipeline import (
    FixedExtractor,
    create_approval,
    create_extraction_draft,
    create_pdf,
    make_config,
)


class _FakeRedcapProject:
    """Minimal in-memory REDCap project double; no network involved."""

    def __init__(self) -> None:
        self.imported: list[dict[str, Any]] | None = None

    def export_metadata(self, format_type: str = "json") -> list[dict[str, Any]]:
        return []

    def import_metadata(self, to_import: list[dict[str, Any]], import_format: str = "json") -> int:
        self.imported = to_import
        return len(to_import)


def test_full_pipeline_from_pdf_intake_to_every_export_format(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    pdf_path = config.inbox_directory / "demo.pdf"
    create_pdf(pdf_path)
    approval = create_approval(pdf_path)
    pdf_path.with_suffix(".pdf.source.json").write_text(
        approval.model_dump_json(), encoding="utf-8"
    )

    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_extraction_draft()),
        allow_remote_processing=True,
    )
    draft = asyncio.run(pipeline.process_file(pdf_path))
    assert draft.status == "catalogued"
    assert draft.catalogue_json_path is not None

    store = QuestionnaireCatalogStore(config.catalogue_directory)
    records = store.load()
    assert [family.instrument_id for family, _path in records] == ["demo_scale"]
    family, _path = records[0]
    version = family.versions[0]
    assert version.source_documents, "Promotion must attach the reviewed rights sidecar"

    search_engine = QuestionnaireSearchEngine(config.catalogue_directory)
    matches = search_engine.search_items("supported")
    assert any(match.instrument_name == family.name_full for match in matches)

    psymetriq_json = export_psymetriq_json([family])
    assert import_psymetriq_json(psymetriq_json) == [family]

    fhir_resource = export_fhir_questionnaire(family, version)
    imported_fhir = import_fhir_questionnaire(fhir_resource)
    assert imported_fhir.versions[0].items[0].prompt_text == version.items[0].prompt_text

    redcap_csv = export_redcap_data_dictionary(family, version)
    imported_redcap = import_redcap_data_dictionary(redcap_csv, language=version.language)
    assert imported_redcap.versions[0].items[0].prompt_text == version.items[0].prompt_text

    item_csv = export_item_csv(family, version)
    assert version.items[0].item_id in item_csv

    workbook_bytes = export_questionnaire_xlsx(family, version)
    assert workbook_bytes[:2] == b"PK"  # a real .xlsx (zip) file, not an empty stub

    project = _FakeRedcapProject()
    push_result = push_questionnaire_to_project(project, family, version)
    assert push_result.pushed_field_count >= 1
    assert project.imported is not None
    pushed_field_names = {record["field_name"] for record in project.imported}
    assert version.items[0].variable_name in pushed_field_names


def test_incomplete_rights_review_blocks_promotion_even_with_a_high_confidence_extraction(
    tmp_path: Path,
) -> None:
    """A safety-property regression guard spanning the whole intake pipeline.

    Even a complete, high-confidence extraction must not reach the shared
    catalogue without an explicit, exact-hash-matched rights sidecar -- this
    is the property every other feature built this project (Zotero sync,
    license profiles) is careful never to bypass.
    """
    config = make_config(tmp_path)
    pdf_path = config.inbox_directory / "demo.pdf"
    create_pdf(pdf_path)
    # Deliberately no <pdf>.source.json sidecar this time.

    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_extraction_draft()),
        allow_remote_processing=True,
    )
    draft = asyncio.run(pipeline.process_file(pdf_path))

    assert draft.status == "review_required"
    assert draft.catalogue_json_path is None
    assert not list(config.catalogue_directory.glob("*.json"))
    assert any("rights" in warning.casefold() for warning in draft.warnings)
