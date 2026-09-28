# User Manual

## Scope

The current runnable workflow covers the data model, synthetic fixture generation, local file-backed search, and a Flet workspace for questionnaire assembly, projects, settings, format exchange, and PDF intake. XLSX review workbooks and reasoned study-specific item adaptations are supported. Similarity warnings, Zotero sync, live REDCap upload, Unipark interchange, and R syntax export remain planned.

## Prerequisites

- Python 3.11 or newer.
- A virtual environment keeps project dependencies isolated.
- Open PowerShell and move to the cloned repository. Replace the path if you cloned PsyMetriQ elsewhere:

```powershell
cd "$HOME\Documents\GitHub\PsyMetriQ"
```

- Create the environment once, then install the dependencies into it:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `.venv` already exists, do not recreate it; update dependencies when `requirements.txt` changes by rerunning the install command. The current workflow requires Python 3.11+, Pydantic v2, and Flet 1.x. No API key or database is needed to launch the local workspace or browse the checked-in catalogue.

To use remote PDF extraction, configure the provider key in the ignored local `.env`, enable remote processing in the GUI, and confirm each run. AlpineAI SwissGPT uses `ALPINEAI_API_KEY` and its documented `https://api.prod.alpineai.ch/v1` endpoint by default. The settings screen can fetch account-visible model IDs; the model ID is also editable.

## Launch the GUI workspace

### From PowerShell

1. Open PowerShell and enter the repository root (skip this if PowerShell already opened there):

```powershell
cd "$HOME\Documents\GitHub\PsyMetriQ"
```

2. Activate the environment for this terminal session:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation because of its execution policy, do not change the machine policy just for PsyMetriQ. Run the virtual-environment interpreter directly instead, as shown below.

3. Start the desktop workspace:

```powershell
python -m src.gui.main
```

4. Stop it when finished: focus the PowerShell window and press `Ctrl+C`, or close the desktop app window. The command prompt returns when the process exits.

To use a browser instead of a desktop window, start the local web server:

```powershell
python -m src.gui.main --web --host 127.0.0.1 --port 8550
```

Open `http://127.0.0.1:8550/` in a browser. The server keeps running after you close that tab. To stop it, return to the same PowerShell window where the command is running and press `Ctrl+C`. To restart it, run the same command again. If port `8550` is already occupied, use another port, for example `--port 8551`, and open `http://127.0.0.1:8551/`.

The steps for browser mode are: (1) run the `--web` command in a terminal, (2) open the printed/local URL in a browser, (3) leave that terminal running while using the app, and (4) press `Ctrl+C` in that terminal to stop the server. Closing the browser tab is not a stop command.

Without environment activation, use the interpreter by its repository-relative path:

```powershell
.\.venv\Scripts\python.exe -m src.gui.main
.\.venv\Scripts\python.exe -m src.gui.main --web --host 127.0.0.1 --port 8550
```

### From VS Code

1. Open the repository folder in VS Code: **File > Open Folder...** and choose `PsyMetriQ`. Alternatively, from PowerShell run `code .` while the current directory is the repository root.
2. Select the project interpreter: press `Ctrl+Shift+P`, run **Python: Select Interpreter**, and choose `.venv` (Python 3.11).
3. Open VS Code's integrated terminal with **Terminal > New Terminal**. Confirm the terminal's current directory is the repository root. If not, run the `cd` command above.
4. In the integrated PowerShell terminal, activate the environment from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, use the explicit interpreter commands above; do not change the machine execution policy.
5. Run `python -m src.gui.main` for the desktop app, or the `--web` command to serve the browser version. VS Code does not need to run as Administrator.
6. To stop a terminal-launched app/server, focus that integrated terminal and press `Ctrl+C`. Closing a browser tab alone does not stop the web server. No separate VS Code Run and Debug configuration is required; start the module from the integrated terminal as shown.

Use the left navigation for the instrument library, project, import/export, PDF intake, and settings. Every primary field/action has an information button with an explanation and example. See the [GUI workspace guide](gui_workspace.md) for complete workflows and file-format coverage.

### Start and stop checklist

| Mode | Start | Stop |
| --- | --- | --- |
| Desktop from terminal or VS Code terminal | `python -m src.gui.main` | Press `Ctrl+C` in that terminal or close the desktop window. |
| Browser from terminal or VS Code terminal | `python -m src.gui.main --web --host 127.0.0.1 --port 8550` | Press `Ctrl+C` in the terminal running the server. Closing the browser tab does not stop it. |

The browser URL is `http://127.0.0.1:8550/`. If that port is occupied, choose a different `--port` and use the matching URL. Re-run the start command to restart after stopping.

## Changes documented in this manual

- The Flet workspace supports faceted instrument search, detailed version/item/response/scoring inspection, item and whole-scale selection, saved projects, and study-specific wording adaptations separated from source records.
- Exchange supports PsyMetriQ JSON, FHIR R4, XLSX review workbooks, item CSV, and REDCap Data Dictionary CSV. Unipark and live REDCap API upload remain unsupported.
- The catalog contains item-bearing Rosenberg Self-Esteem Scale data and searchable, non-selectable WHO-5/WEMWBS link-only metadata profiles; the latter do not include item text.
- Remote extraction offers OpenAI, Anthropic, AlpineAI SwissGPT, and generic OpenAI-compatible providers. Provider model lists can be queried without transmitting a PDF; remote PDF extraction remains opt-in and separately confirmed.
- AlpineAI follows its documented basic Chat Completions API; extraction JSON is validated locally because Structured Outputs compatibility is not documented.

## Generate development fixtures

From the repository root, run:

```powershell
python data/generate_mock_data.py
```

The command writes `bdi_ii_demo.json` and `asrs_demo.json` into `data/02_extracted_jsons/` and logs each output path. The fixture text is fabricated, inspired only at a high level by the named domains, and is not copied from the instruments. These files are deterministic development examples, not clinically valid questionnaires.

The generator overwrites those two named demo files on each run. It does not delete other files. The output directory is configurable when calling `generate_mock_data(output_directory: Path)` from Python, which is useful for tests and tooling.

## Build the real instrument test catalog

The repository includes PHQ-9/GAD-7, DASS/DASS-Y, and IPAQ source forms with explicit redistribution terms. Rebuild their structured JSON and PDF checksums with:

```powershell
python data/questionnaires/build_catalog.py
python data/questionnaires/build_dass_catalog.py
python data/questionnaires/build_ipaq_catalog.py
python data/questionnaires/build_wellbeing_catalog.py
```

The form-builder commands read only PDFs already present under `data/questionnaires/forms/`; they do not download or overwrite source documents. They write five form-bearing families. The wellbeing builder adds the public-domain Rosenberg record and metadata-only WHO-5/WEMWBS profiles. Review the [instrument data and rights notes](../data/questionnaires/README.md) before adding or sharing any other instrument.

## Import New PDFs

Drop a PDF into `data/questionnaires/inbox/`, then process once or run the local watcher:

```powershell
python -m src.ingestion.document_pipeline
python -m src.ingestion.document_pipeline --watch
```

The default flow extracts text/metadata locally, attempts OCR for scans if installed, classifies a domain, and creates a private Pydantic review draft. It does not send PDF text to the cloud. For remote extraction, choose `openai`, `anthropic`, `alpineai`, or `openai-compatible` with `--provider`, configure the corresponding key in the ignored local `.env`, verify privacy/rights conditions, and opt in explicitly with `--allow-remote-processing`. AlpineAI SwissGPT uses `ALPINEAI_API_KEY` and defaults to its documented endpoint; the GUI model picker or CLI `--model` selects an account-visible model. Generic compatible services need an endpoint and model from their service owner. Never send confidential or non-transmittable material.

New/uncertain documents are moved to the Git-ignored `data/questionnaires/review/` tree. To auto-promote a complete candidate into shared `forms/` and family JSON, an authorized reviewer must check the exact items and create a hash-matched `<filename>.pdf.source.json` sidecar using [the example template](../data/questionnaires/source_approval.example.json). After correcting the review draft and placing the sidecar beside its PDF, promote locally without a second model call:

```powershell
python -m src.ingestion.document_pipeline --approve-draft data/questionnaires/review/drafts/<sha256>.json
```

The importer refuses unknown rights, hash mismatches, low confidence, incomplete forms, scanned pages without usable OCR, or version conflicts. See the [full intake guide](pdf_intake.md) for stages, limits, manual review, and file-placement rules.

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
pytest tests/unit/test_instrument_catalog.py -q
ruff check schemas/questionnaire_schema.py data/generate_mock_data.py src/core/search_engine.py data/questionnaires/ tests/unit/
```

The tests cover REDCap variable-name boundaries, duplicate identifiers, missing references, JSON serialization round-trips, synthetic output validity, logged filesystem failures, search matches, reload behavior, and invalid shared files.

## Data and credentials

Never place participant data, private source PDFs, API keys, access tokens, or production exports in the demo data directory. See the [security guide](security.md) before configuring integrations or staging files for Git.
