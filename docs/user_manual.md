# User Manual

## Scope

The current runnable workflow covers the data model, synthetic fixture generation, and local file-backed search. Questionnaire assembly in a GUI, similarity warnings, PDF/LLM ingestion, and REDCap upload are planned features.

## Prerequisites

- Python 3.11 or newer.
- A virtual environment is recommended so project dependencies remain isolated.
- Install the project dependencies from the repository root when setting up the complete development environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The current implemented workflow requires Pydantic v2. No API key or database installation is needed to generate or search local synthetic fixtures.

## Generate development fixtures

From the repository root, run:

```powershell
python data/generate_mock_data.py
```

The command writes `bdi_ii_demo.json` and `asrs_demo.json` into `data/02_extracted_jsons/` and logs each output path. The fixture text is fabricated, inspired only at a high level by the named domains, and is not copied from the instruments. These files are deterministic development examples, not clinically valid questionnaires.

The generator overwrites those two named demo files on each run. It does not delete other files. The output directory is configurable when calling `generate_mock_data(output_directory: Path)` from Python, which is useful for tests and tooling.

## Search a shared folder

Point the search engine at the directory containing validated questionnaire JSON files:

```python
from pathlib import Path

from src.core.search_engine import QuestionnaireSearchEngine

search_engine = QuestionnaireSearchEngine(Path("data/02_extracted_jsons"))
matches = search_engine.search_items("attention")
for match in matches:
	print(match.match_type, match.instrument_name, match.item_id)
```

The service validates the files at startup and keeps them in memory; it does not create a database or modify JSON. Search includes instrument and version names, language, locale, form type, variant types, population labels, contributors, provenance, item dimensions/text, and response labels. Call `search_engine.reload()` after the shared directory changes. If any file is unreadable, invalid, or duplicates an instrument ID, the operation logs the error and raises `QuestionnaireDataError`. A failed reload leaves the last valid search state intact.

Keywords, aliases, MeSH descriptors/IDs, characteristics, and notes are searchable in metadata attached to the instrument, a version, or an item. Family metadata is appropriate for concepts common to all variants; place version- or item-specific tags at their own level.

Combine free text with structured filters, or omit text to list items that match the selected facets:

```python
from pathlib import Path

from src.core.search_engine import QuestionnaireSearchEngine, QuestionnaireSearchFilters

search_engine = QuestionnaireSearchEngine(Path("data/02_extracted_jsons"))
filters = QuestionnaireSearchFilters(
	languages=["de"],
	locales=["de-DE", "de-CH"],
	form_types=["short"],
	target_populations=["adolescents"],
	keywords=["attention", "executive function"],
	mesh_terms=["D001"],
	characteristics=["self-report"],
	is_commercial=False,
)
matches = search_engine.search_items("focus", filters)
```

Within one filter field, selected values are alternatives; separate fields are combined. For example, a match must be German, in one of the selected locales, a short form, for adolescents, and satisfy each selected metadata category. `keywords`, MeSH terms, and characteristics match stored values exactly and case-insensitively; free text also searches aliases and notes.

For team use, point the service at an access-controlled synchronized folder or share reviewed JSON files through a private repository. The repository's `data/02_extracted_jsons/` folder is configured to include only the two synthetic demos; real extracted material is ignored by default.

## Validate the schema changes

Run the focused tests and lint check from the repository root:

```powershell
pytest tests/unit/test_schema.py -q
pytest tests/unit/test_search_engine.py -q
ruff check schemas/questionnaire_schema.py data/generate_mock_data.py src/core/search_engine.py tests/unit/
```

The tests cover REDCap variable-name boundaries, duplicate identifiers, missing references, JSON serialization round-trips, synthetic output validity, logged filesystem failures, search matches, reload behavior, and invalid shared files.

## Data and credentials

Never place participant data, private source PDFs, API keys, access tokens, or production exports in the demo data directory. See the [security guide](security.md) before configuring integrations or staging files for Git.
