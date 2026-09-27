# PsyMetriQ

PsyMetriQ is an open-source research tool for cataloguing, comparing, assembling, and eventually exporting psychometric questionnaires. Its data model keeps an instrument family separate from each concrete form, so translations, locales, revisions, short forms, target groups, contributors, validation sources, and licensing provenance remain distinguishable.

> PsyMetriQ is a research and data-management tool, not a diagnostic device. Screening scores do not establish a diagnosis, and the bundled example instruments do not replace clinical judgment or their official manuals.

## Current state

Implemented:

- Pydantic v2 models for questionnaire families, concrete versions, items, response scales, scoring, population, provenance, metadata, and source documents.
- Portable JSON file catalog with case-insensitive search and composable filters; no database server or database file is required.
- A permission-reviewed test corpus with the official PHQ-9 English and Germany-German forms and GAD-7 English, Austrian-German, and Swiss-German forms.
- PDF SHA-256 verification, source links, retrieval dates, and explicit redistribution basis in the JSON records.

Planned: the Flet search/assembly GUI, NLP redundancy review, Zotero/PDF/LLM ingestion, and REDCap/R exporters. The backend search API is ready for GUI integration, but the GUI does not yet implement the search controls.

## Quick Start

Python 3.11 or newer is recommended. In PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Generate the two synthetic development examples:

```powershell
python data/generate_mock_data.py
```

Generate or refresh the real, permission-cleared PHQ-9/GAD-7 catalog from the PDFs already bundled in the repository:

```powershell
python data/questionnaires/build_catalog.py
```

The builder never downloads files. It validates the existing PDF files, calculates checksums, and writes Pydantic-validated JSON into `data/questionnaires/json/`.

Search the catalog from Python:

```python
from pathlib import Path

from src.core.search_engine import QuestionnaireSearchEngine, QuestionnaireSearchFilters

engine = QuestionnaireSearchEngine(Path("data/questionnaires/json"))
filters = QuestionnaireSearchFilters(languages=["de"], locales=["de-CH"])
results = engine.search_items("Sorgen", filters)
```

Filters are exact, case-insensitive facets. Multiple values within a facet are alternatives; distinct facets must all match. Free text can be combined with facets, and facets alone return matching item records. Call `engine.reload()` after shared JSON files change.

## Verification

```powershell
pytest -q
ruff check .
```

A repository-wide Ruff check may report pre-existing style issues in unfinished modules. Use the focused check listed in [docs/testing.md](docs/testing.md) when validating a specific change.

## Real Instrument Data and Rights

Only the PHQ-9 and GAD-7 forms listed in [data/questionnaires/README.md](data/questionnaires/README.md) are currently bundled as real item text and PDFs. The official PHQ Screeners source explicitly permits reproduction, translation, display, and distribution of its PHQ/GAD-7 screeners and translations. Each PDF has a source URL, permission statement, retrieval date, and SHA-256 checksum in its JSON record.

Other well-known instruments are listed in the [instrument library and licensing guide](docs/instrument_library.md), but are not copied into this repository until the exact instrument/version/translation redistribution rights are verified. A public download link, university access, or a non-commercial user licence is not permission to redistribute a PDF or item text on GitHub. Never add participant responses, private study files, credentials, or unapproved licensed material.

## Documentation

- [Documentation index](docs/README.md)
- [Software overview](docs/software_overview.md)
- [Architecture](docs/architecture.md)
- [Questionnaire domain model](docs/domain_data_model.md)
- [User manual](docs/user_manual.md)
- [Instrument library and licensing](docs/instrument_library.md)
- [Security](docs/security.md)
- [Coding guidelines](docs/coding_guidelines.md)
- [Testing strategy](docs/testing.md)

The original architecture brief remains in [psymetriq_readme.md](psymetriq_readme.md); this root README describes the current implementation and supported commands.
