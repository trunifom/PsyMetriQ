# User Manual

## Scope

The current runnable workflow covers the Phase-1 data model and synthetic fixture generation. Search, questionnaire assembly in a GUI, similarity warnings, PDF/LLM ingestion, and REDCap upload are not documented as available commands yet; they are planned features.

## Prerequisites

- Python 3.11 or newer.
- A virtual environment is recommended so project dependencies remain isolated.
- Install the project dependencies from the repository root when setting up the complete development environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Phase 1 itself requires Pydantic v2. No API key is needed to generate the local synthetic fixtures.

## Generate development fixtures

From the repository root, run:

```powershell
python data/generate_mock_data.py
```

The command writes `bdi_ii_demo.json` and `asrs_demo.json` into `data/02_extracted_jsons/` and logs each output path. The fixture text is fabricated, inspired only at a high level by the named domains, and is not copied from the instruments. These files are deterministic development examples, not clinically valid questionnaires.

The generator overwrites those two named demo files on each run. It does not delete other files. The output directory is configurable when calling `generate_mock_data(output_directory: Path)` from Python, which is useful for tests and tooling.

## Validate the schema changes

Run the focused tests and lint check from the repository root:

```powershell
pytest tests/unit/test_schema.py -q
ruff check schemas/questionnaire_schema.py data/generate_mock_data.py tests/unit/test_schema.py
```

The tests cover REDCap variable-name boundaries, duplicate identifiers, missing references, JSON serialization round-trips, synthetic output validity, and logged filesystem failures.

## Data and credentials

Never place participant data, private source PDFs, API keys, access tokens, or production exports in the demo data directory. See the [security guide](security.md) before configuring integrations or staging files for Git.
