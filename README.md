# PsyMetriQ

PsyMetriQ is an open-source research tool for cataloguing, comparing, assembling, and eventually exporting psychometric questionnaires. Its data model keeps an instrument family separate from each concrete form, so translations, locales, revisions, short forms, target groups, contributors, validation sources, and licensing provenance remain distinguishable.

> PsyMetriQ is a research and data-management tool, not a diagnostic device. Screening scores do not establish a diagnosis, and the bundled example instruments do not replace clinical judgment or their official manuals.

## Current state

Implemented:

- Pydantic v2 models for questionnaire families, concrete versions, items, response scales, scoring, population, provenance, metadata, and source documents.
- Portable JSON file catalog with case-insensitive search and composable filters; no database server or database file is required.
- A rights-reviewed real-form corpus: PHQ-9 (English/Germany-German), GAD-7 (English/Austria-/Switzerland-German), DASS-21 (English/German), DASS-Y (English/German; ages 8-17), and IPAQ short forms (English/German; ages 15-69) plus IPAQ-E (older-adult English form).
- PDF SHA-256 verification, source links, retrieval dates, and explicit redistribution basis in the JSON records.
- A local PDF inbox with text extraction/OCR, heuristic domain routing, optional opt-in OpenAI, Anthropic, or OpenAI-compatible LLM extraction, private review drafts, and checksum-bound rights-gated promotion for questionnaire forms and validation-study references.
- Read-only Python search connectors for NIH CDE question/response previews, NLM LOINC display terms, and PubMed citation metadata. These are source-linked suggestions, not catalogue entries; the current GUI does not expose them.

Planned: the Flet search/assembly GUI, NLP redundancy review, Zotero sync, and REDCap/R exporters. The PDF intake vertical slice is usable from the CLI but not yet exposed in the GUI.

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

Generate or refresh the real catalog from PDFs already bundled in the repository:

```powershell
python data/questionnaires/build_catalog.py
python data/questionnaires/build_dass_catalog.py
python data/questionnaires/build_ipaq_catalog.py
```

The builders never download files. They validate existing PDFs, calculate checksums, and write Pydantic-validated JSON into `data/questionnaires/json/`. The licensed original forms are organized under `data/questionnaires/forms/<domain>/<instrument>/`.

Import a new PDF by dropping it into `data/questionnaires/inbox/`:

```powershell
python -m src.ingestion.document_pipeline
python -m src.ingestion.document_pipeline --watch
```

By default extraction stays local and unapproved documents produce review drafts. Optional OpenAI extraction requires a local `OPENAI_API_KEY` and the explicit `--allow-remote-processing` flag. Questionnaire promotion requires a human-reviewed, SHA-256-bound rights/content sidecar; validation-study promotion uses a separate citation-review attestation and reference catalog. See the [PDF intake guide](data/questionnaires/inbox/README.md) and [full workflow documentation](docs/pdf_intake.md).

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

The PHQ-9/GAD-7 forms are redistributed under the official PHQ Screeners notice; DASS/DASS-Y forms are public domain but cannot be modified or sold; IPAQ forms are redistributed under CC BY 4.0. Each is attributed separately, linked to its exact official source, and recorded with the relevant permission conditions and PDF SHA-256 checksum. German DASS/IPAQ translation quality is not guaranteed by the source organizations; the JSON preserves the exact variant and states this limitation.

Other well-known instruments are listed in the [instrument library and licensing guide](docs/instrument_library.md), but remain link-only until exact version/translation rights are verified. A public download link, university access, or non-commercial use licence is not automatically permission to redistribute a PDF or item text on GitHub. Never add participant responses, private study files, credentials, or unapproved licensed material.

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
