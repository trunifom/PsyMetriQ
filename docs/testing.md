# Testing Strategy

## Purpose

Tests protect data integrity first, then module contracts and end-to-end user workflows. Coverage should follow risk: validation rules and file-backed search need focused unit tests; API, asynchronous, and GUI behavior need boundary or integration tests as those phases are implemented.

## Test layers

- **Unit tests (`tests/unit/`):** fast, deterministic checks for Pydantic models, validators, pure transformations, view-model state, and error handling. Use temporary directories and synthetic values.
- **Integration tests (`tests/integration/`):** verify real module boundaries such as loading multiple shared JSON files, exporter request construction, or GUI-to-view-model flows. Isolate external APIs and credentials behind fakes or mocks by default.
- **Manual acceptance checks:** use only a controlled non-production environment for interactive GUI or remote API behavior that is not reliably covered by automation.

## Phase-1 checks

The schema suite verifies valid model construction, invalid REDCap variable names, duplicate item and version IDs, case-insensitive field-name collisions, missing response-set and scoring-item references, language/locale syntax, population age ranges, version ancestry and cycles, Pydantic JSON round-tripping, generated fixture validation, and safe reporting of filesystem failures. The search suite verifies matching across entity types and metadata scopes, aliases, MeSH terms, notes, exact filters, combined AND/OR semantics, blank and missing results, refreshes, malformed files, duplicate instruments, and preservation of the last valid view.

The real-instrument catalog suite validates PHQ-9/GAD-7/DASS/DASS-Y/IPAQ item counts, exact transcribed wording, locale and age coverage, non-comparable youth scoring, DASS multipliers, numeric IPAQ units, official redistribution records, local PDF paths, SHA-256 digests, and search over generated language variants.

The PDF intake suite uses generated local PDFs and fake extraction responses. It tests searchable text/metadata/checksum extraction, OCR-required routing, private review behavior, hash-bound human approval, safe questionnaire and study-reference promotion, sidecar mismatch rejection, symlink/out-of-inbox protection, LLM-license-claim stripping, batch continuation after failures, and that the closed Structured Outputs DTO maps into canonical domain models without making a network request.

Run from the repository root:

```powershell
pytest tests/unit/test_schema.py -q
pytest tests/unit/test_search_engine.py -q
pytest tests/unit/test_instrument_catalog.py -q
ruff check schemas/questionnaire_schema.py data/generate_mock_data.py src/core/search_engine.py data/questionnaires/ tests/unit/
pytest tests/unit/test_document_pipeline.py -q
ruff check src/ingestion/ tests/unit/test_document_pipeline.py
pytest tests/unit/test_external_sources.py -q
ruff check src/core/external_sources.py src/core/external_search_cli.py tests/unit/test_external_sources.py
```

## Expectations for future features

- Test normal behavior and expected invalid inputs for every public service operation.
- Exercise failure behavior for unavailable files, malformed JSON, duplicate identifiers, API timeouts, authentication rejection, rate limits, and partial writes where relevant.
- Test async cancellation and confirm expensive or blocking work does not run on the UI event loop.
- Keep tests independent of real API keys, live user accounts, private PDFs, and participant records.
- Use deterministic fake model outputs for NLP and LLM tests; test external integration contracts separately in an explicitly configured environment.
- Run the complete test suite and lint checks before a task is committed when feasible. Record any unavailable gate and why it could not run.
