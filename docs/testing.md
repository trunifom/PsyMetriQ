# Testing Strategy

## Purpose

Tests protect data integrity first, then module contracts and end-to-end user workflows. Coverage should follow risk: validation rules need focused unit tests; database, API, asynchronous, and GUI behavior need boundary or integration tests as those phases are implemented.

## Test layers

- **Unit tests (`tests/unit/`):** fast, deterministic checks for Pydantic models, validators, pure transformations, view-model state, and error handling. Use temporary directories and synthetic values.
- **Integration tests (`tests/integration/`):** verify real module boundaries such as JSON loading into DuckDB, exporter request construction, or GUI-to-view-model flows. Isolate external APIs and credentials behind fakes or mocks by default.
- **Manual acceptance checks:** use only a controlled non-production environment for interactive GUI or remote API behavior that is not reliably covered by automation.

## Phase-1 checks

The schema suite verifies valid model construction, invalid REDCap variable names, duplicate item and version IDs, case-insensitive field-name collisions, missing response-set and scoring-item references, Pydantic JSON round-tripping, generated fixture validation, and safe reporting of filesystem failures.

Run from the repository root:

```powershell
pytest tests/unit/test_schema.py -q
ruff check schemas/questionnaire_schema.py data/generate_mock_data.py tests/unit/test_schema.py
```

## Expectations for future features

- Test normal behavior and expected invalid inputs for every public service operation.
- Exercise failure behavior for unavailable files, malformed JSON, database errors, API timeouts, authentication rejection, rate limits, and partial writes where relevant.
- Test async cancellation and confirm expensive or blocking work does not run on the UI event loop.
- Keep tests independent of real API keys, live user accounts, private PDFs, and participant records.
- Use deterministic fake model outputs for NLP and LLM tests; test external integration contracts separately in an explicitly configured environment.
- Run the complete test suite and lint checks before a task is committed when feasible. Record any unavailable gate and why it could not run.
