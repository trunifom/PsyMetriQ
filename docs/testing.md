# Testing Strategy

## Purpose

Tests protect data integrity first, then module contracts and end-to-end user workflows. Coverage should follow risk: validation rules and file-backed search need focused unit tests; API, asynchronous, and GUI behavior need boundary or integration tests as those phases are implemented.

## Test layers

- **Unit tests (`tests/unit/`):** fast, deterministic checks for Pydantic models, validators, pure transformations, view-model state, and error handling. Use temporary directories and synthetic values.
- **Integration tests (`tests/integration/`):** verify real module boundaries such as loading multiple shared JSON files, exporter request construction, or GUI-to-view-model flows. Isolate external APIs and credentials behind fakes or mocks by default.
- **Manual acceptance checks:** use only a controlled non-production environment for interactive GUI or remote API behavior that is not reliably covered by automation.

## Phase-1 checks

The schema suite verifies valid model construction, invalid REDCap variable names, duplicate item and version IDs, case-insensitive field-name collisions, missing response-set and scoring-item references, language/locale syntax, population age ranges, version ancestry and cycles, Pydantic JSON round-tripping, generated fixture validation, and safe reporting of filesystem failures. The search suite verifies matching across entity types and metadata scopes, aliases, MeSH terms, notes, exact filters, combined AND/OR semantics, blank and missing results, refreshes, malformed files, duplicate instruments, and preservation of the last valid view.

The real-instrument catalog suite validates PHQ-9/GAD-7/DASS/DASS-Y/IPAQ item counts, exact transcribed wording, locale and age coverage, non-comparable youth scoring, DASS multipliers, numeric IPAQ units, official redistribution records, local PDF paths, SHA-256 digests, and search over generated language variants. The wellbeing builder/catalog tests validate the public-domain Rosenberg items and the WHO-5/WEMWBS/SWEMWBS/GSE/PSS selectable metadata references, source-reported lengths/dimensions, and license facets without embedding unverified item wording.

The PDF intake suite uses generated local PDFs and fake extraction responses. It tests searchable text/metadata/checksum extraction, OCR-required routing, private review behavior, hash-bound human approval, safe questionnaire and study-reference promotion, sidecar mismatch rejection, symlink/out-of-inbox protection, LLM-license-claim stripping, batch continuation after failures, and that the closed Structured Outputs DTO maps into canonical domain models without making a network request.

`tests/integration/test_pipeline_to_export.py` drives the real modules together end-to-end through one isolated temporary project root, reusing the PDF/approval/extractor fixtures from `test_document_pipeline.py` rather than re-deriving them: a synthetic PDF with a matching rights sidecar is ingested by the real `QuestionnaireDocumentPipeline` (only the LLM call is a fixed extractor; no network), promoted into a real catalogue JSON file, loaded back through the real `QuestionnaireCatalogStore` and `QuestionnaireSearchEngine`, and exported through every file-based format (PsyMetriQ JSON, FHIR, REDCap CSV, item CSV, XLSX) plus a fake, in-memory live REDCap push. A second test is a regression guard for the project's core safety property: a complete, high-confidence extraction with no rights sidecar must still be refused promotion and stay in local review, never reaching the shared catalogue.

Run from the repository root:

```powershell
pytest tests/unit/test_schema.py -q
pytest tests/unit/test_search_engine.py -q
pytest tests/unit/test_instrument_catalog.py -q
ruff check schemas/questionnaire_schema.py data/generate_mock_data.py src/core/search_engine.py data/questionnaires/ tests/unit/
pytest tests/unit/test_document_pipeline.py -q
ruff check src/ingestion/ tests/unit/test_document_pipeline.py
pytest tests/unit/test_llm_providers.py tests/unit/test_provider_models.py -q
ruff check src/ingestion/llm_extractor.py src/ingestion/provider_models.py tests/unit/test_llm_providers.py tests/unit/test_provider_models.py
pytest tests/unit/test_gui_application.py tests/unit/test_gui_workspace.py -q
pytest tests/unit/test_external_sources.py -q
ruff check src/core/external_sources.py src/core/external_search_cli.py tests/unit/test_external_sources.py
pytest tests/unit/test_data_exchange.py -q
pytest tests/unit/test_gui_workspace.py tests/unit/test_catalog_store.py tests/unit/test_gui_application.py -q
ruff check src/exporters/data_exchange.py src/gui/ tests/unit/test_data_exchange.py tests/unit/test_gui_workspace.py tests/unit/test_catalog_store.py tests/unit/test_gui_application.py
pytest tests/integration/ -q
```

## Expectations for future features

- Test normal behavior and expected invalid inputs for every public service operation.
- Exercise failure behavior for unavailable files, malformed JSON, duplicate identifiers, API timeouts, authentication rejection, rate limits, and partial writes where relevant.
- Test async cancellation and confirm expensive or blocking work does not run on the UI event loop.
- Keep tests independent of real API keys, live user accounts, private PDFs, and participant records.
- Use deterministic fake model outputs for NLP and LLM tests; test external integration contracts separately in an explicitly configured environment.
- Run the complete test suite and lint checks before a task is committed when feasible. Record any unavailable gate and why it could not run.
