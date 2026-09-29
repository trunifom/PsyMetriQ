# PsyMetriQ

PsyMetriQ is an open-source research tool for cataloguing, comparing, assembling, and exporting psychometric questionnaires. Its data model keeps an instrument family separate from each concrete form, so translations, locales, revisions, short forms, target groups, contributors, validation sources, and licensing provenance remain distinguishable.

> PsyMetriQ is a research and data-management tool, not a diagnostic device. Screening scores do not establish a diagnosis, and the bundled example instruments do not replace clinical judgment or their official manuals.

## Current state

Implemented:

- Pydantic v2 models for questionnaire families, concrete versions, items, response scales, scoring, population, provenance, metadata, and source documents.
- Portable JSON file catalog with case-insensitive search and composable filters; no database server or database file is required.
- A real-form catalogue: PHQ-9, GAD-7, DASS-21, DASS-Y, IPAQ and the English public-domain Rosenberg Self-Esteem Scale have item-bearing records. WHO-5, WEMWBS/SWEMWBS, GSE and PSS are searchable, selectable metadata references with source-reported dimensions/length and explicit rights notes; reference selection does not include or authorize item wording.
- PDF SHA-256 verification, source links, retrieval dates, and explicit redistribution basis in the JSON records.
- A local PDF inbox with text extraction/OCR, heuristic domain routing, optional opt-in OpenAI, Anthropic, AlpineAI SwissGPT, or OpenAI-compatible LLM extraction, private review drafts, and checksum-bound rights-gated promotion for questionnaire forms and validation-study references.
- A Flet workspace for faceted catalogue search, detailed item/response/source inspection, whole-scale/item selection, reasoned study-only adaptations, saved projects/settings, PDF intake, and ZIP exchange containing PsyMetriQ JSON, FHIR R4, XLSX workbooks, item CSV, or REDCap Data Dictionary CSV. Public NIH CDE/LOINC/PubMed discovery is still available from Python/CLI, not yet embedded in the GUI.

A Zotero attachment sync (`python -m src.ingestion.zotero_source`) stages PDFs from a Zotero library into the intake inbox; downloaded files still require the same human rights sidecar as any other inbox PDF. The GUI can also push the other direction: export a selected version and create a Zotero reference item for it (with the export file attached), independent of and without altering any redistribution rights. REDCap now also supports a live project connection (`src/exporters/redcap_api.py`, wired into **Import & Export**): connect with a project API URL/token, push a selected version's fields (always collision-checked and merged against the project's existing data dictionary, never overwriting it), or pull an entire project's data dictionary straight into the local catalogue. The REDCap exporter/importer also handles `slider` fields, emits `calc` fields for scoring algorithms (with explicit, reverse-scoring-aware recoding), and never silently drops an unsupported REDCap field type on import. A base-R scoring-syntax export (`r_syntax`) is also available, applying the identical reverse-scoring recode logic. `ItemSchema` also models simple branching logic (`show_if`, AND-only equality/inequality conditions) and matrix grouping, exported to/imported from REDCap's Data Dictionary; unparseable branching logic (`or`, parentheses, unresolvable fields) is preserved as text rather than guessed at. A semantic construct-similarity check (`src/core/nlp_engine.py`, local sentence-transformers) surfaces candidate "jingle-jangle" instrument overlaps in the library dashboard for human review; it changes nothing automatically. A best-effort LimeSurvey TSV export/import (`limesurvey_tsv`) is also available, built and verified against LimeSurvey's own importer source code; unlike REDCap it has not been checked against a live LimeSurvey instance, and the docs say so explicitly. A narrower best-effort Unipark export/import (`unipark_txt`) targets Tivian's own documented "Paste from Word" plain-text convention for text/single/multiple-choice questions only; Unipark's actual project file format is closed-source and undocumented, so matrix questions, internal type codes, and branching are out of scope by design, not by omission. A best-effort Qualtrics QSF export/import (`qualtrics_qsf`) is also available, built and cross-checked against a real, publicly available `.qsf` file rather than written from memory; like LimeSurvey it has not been checked against a live Qualtrics import, covers only single/multiple-choice and text/numeric questions, and does not translate branching or PsyMetriQ scoring algorithms into Qualtrics' own (much less documented) Display Logic and scoring features.
XLSX is an export/review workbook, not an import format. See the [GUI guide](docs/gui_workspace.md) for format fidelity and workflow limits.

## Quick Start

Python 3.11 or newer is recommended. In PowerShell from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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
python data/questionnaires/build_wellbeing_catalog.py
```

The builders never download files. Form builders validate existing PDFs, calculate checksums, and write Pydantic-validated JSON; the wellbeing builder adds the public-domain Rosenberg record and link-only WHO-5/WEMWBS profiles. Licensed original forms are organized under `data/questionnaires/forms/<domain>/<instrument>/`.

Launch the Flet workspace:

```powershell
python -m src.gui.main
```

For a local browser preview:

```powershell
python -m src.gui.main --web --host 127.0.0.1 --port 8550
```

The GUI guide describes projects, settings, imports, exports, and current limitations: [docs/gui_workspace.md](docs/gui_workspace.md).
The [user manual](docs/user_manual.md#launch-the-gui-workspace) has step-by-step terminal and VS Code instructions, including how to stop and restart the desktop/browser app.

The GUI can load the model IDs available to an OpenAI, Anthropic, AlpineAI SwissGPT, or OpenAI-compatible account. For SwissGPT, set `ALPINEAI_API_KEY` in the ignored `.env`; the documented endpoint defaults to `https://api.prod.alpineai.ch/v1`. Model IDs are discovered from the provider rather than frozen in the UI.

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
- [Licensing workflow, Zotero sync, and admin configuration](docs/admin_and_licensing.md)
- [Coding guidelines](docs/coding_guidelines.md)
- [Testing strategy](docs/testing.md)

The original architecture brief remains in [psymetriq_readme.md](psymetriq_readme.md); this root README describes the current implementation and supported commands.
