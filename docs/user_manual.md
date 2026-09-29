# User Manual

## Scope

The current runnable workflow covers the data model, synthetic fixture generation, local file-backed search, and a Flet workspace for questionnaire assembly, projects, settings, format exchange, and PDF intake. XLSX review workbooks and reasoned study-specific item adaptations are supported. A Zotero attachment sync (`src/ingestion/zotero_source.py`) can stage PDFs from a Zotero library into the inbox. Similarity warnings, live REDCap upload, Unipark interchange, and R syntax export remain planned.

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

Display preferences are at the top of **Einstellungen > Darstellung**. Choose Klein, Normal, or Groß for interface text, and use the sun/moon button in the header to switch light/dark design quickly. The choices are stored locally and restored at the next launch.

### Appearance and readability

Use **Klein** when more content should fit on screen, **Normal** for the default layout, and **Groß** when labels, questionnaire names, or form fields need more visual space. The change applies immediately across the current view, including the library, settings fields, status text, and modal dialogs. It is safe to switch levels repeatedly; the application scales from each control's original size rather than multiplying an already scaled value.

The dark design changes both Flet's theme mode and PsyMetriQ's explicit surface, text, border, icon, warning, and error colors. This keeps the library cards and settings panels readable even where the application uses fixed semantic colors. The theme icon remains available in every workspace view, while the switch under **Darstellung** makes the current state visible in the settings form.

The preferences are saved to `data/psymetriq-settings.json` (or the configured local settings path) whenever the header switch, settings switch, or font-size dropdown changes. They are also part of settings export/import. A settings import is applied to the current session but is intentionally not written over the local file until **Einstellungen speichern** is pressed. This prevents inspecting an exchanged settings file from silently changing the local installation.

The relevant JSON fragment is:

```json
{
	"settings_schema_version": 1,
	"theme_mode": "light",
	"font_size": "normal"
}
```

Only the documented values are accepted. If an older settings file omits these two properties, PsyMetriQ uses light design and normal text automatically. If a settings file contains an invalid value, the normal settings validation error is shown and the current valid session remains active.

For very narrow windows, use the browser or operating-system zoom in addition to the application setting. The application keeps the main library columns bounded and allows long instrument names to wrap, but it still requires a usable window size; the desktop minimum is 900 by 650 pixels.

### Start and stop checklist

| Mode | Start | Stop |
| --- | --- | --- |
| Desktop from terminal or VS Code terminal | `python -m src.gui.main` | Press `Ctrl+C` in that terminal or close the desktop window. |
| Browser from terminal or VS Code terminal | `python -m src.gui.main --web --host 127.0.0.1 --port 8550` | Press `Ctrl+C` in the terminal running the server. Closing the browser tab does not stop it. |

The browser URL is `http://127.0.0.1:8550/`. If that port is occupied, choose a different `--port` and use the matching URL. Re-run the start command to restart after stopping.

For diagnostics, add `--log-level DEBUG` to either start command. For example:

```powershell
python -m src.gui.main --web --host 127.0.0.1 --port 8550 --log-level DEBUG
```

DEBUG logs include Flet session connections, catalogue family/version counts, visible-version counts, safe instrument/version IDs, and render failures. They do not log item wording, document text, or API-key values. Keep the terminal output when reporting a blank/gray view. INFO is the normal default; `PSYMETRIQ_LOG_LEVEL=DEBUG` can also set the default level.

The library uses a bounded version-list viewport with independent scrolling. If the cards disappear again, compare the `visible_versions` count in DEBUG output with the Flet screenshot: a positive count means catalogue/filtering succeeded and the remaining fault is in client layout/rendering; zero points to catalog contents or active filters.

## Changes documented in this manual

- The Flet workspace supports faceted instrument search, detailed version/item/response/scoring inspection, item and whole-scale selection, saved projects, and study-specific wording adaptations separated from source records.
- Exchange supports PsyMetriQ JSON, FHIR R4, XLSX review workbooks, item CSV, REDCap Data Dictionary CSV (plus a live REDCap project connection, Section "REDCap: file export/import and the live API" below), and best-effort LimeSurvey TSV, Unipark paste-text, and Qualtrics QSF export/import (see the matching sections below).
- The catalog contains item-bearing Rosenberg Self-Esteem Scale data and selectable reference profiles for WHO-5, WEMWBS/SWEMWBS, GSE, and PSS. Reference profiles record source-reported length/dimensions and license status but do not contain item wording. They are usable for discovery, meta-analysis planning, and project references; they do not grant item reproduction or administration permission.
- Search accepts regional language tags such as `de-AT` even when the version language is stored as `de`; a `de` filter includes the documented regional German variants. Age facets consolidate source population labels into broad overlapping bands: 0-11, 12-17, 18-64, 65+, and unknown.
- The library supports combined age-group selection, visible active-filter summaries, one-click filter reset, and an instrument profile with source-grounded purpose, construct, name, development, population, publication, psychometric, interpretation, and citation information where the catalog documents it.
- Each catalog version now also exposes administration time, recall period, response format, item structure, scoring workflow, and a psychometric evidence summary. These values are informational source summaries: they do not calculate scores, diagnose participants, or replace the official manual.
- The generated catalog metadata can be refreshed after rebuilding source JSON files with `python data/questionnaires/enrich_catalog_metadata.py`. The enrichment step covers all catalog families, preserves explicit gaps as `Nicht dokumentiert`, and never adds restricted item wording.
- The library search is also an information search: it searches aliases, constructs, citations, target populations, authors, catalog notes, item content, response labels, and the structured instrument-profile fields. Select a result to read its profile before deciding whether to add the version or individual items to a project.
- Age groups are selected independently. Multiple checked groups are alternatives, while language, locale, form type, rights status, and license facets remain combined. The result count and active-filter line provide immediate feedback; **Filter zurücksetzen** restores the complete catalog view.
- The profile distinguishes documented facts from catalog gaps. `Nicht dokumentiert` means that this catalog record has not yet supplied a source-grounded statement. It does not mean that the instrument lacks a purpose, a name history, validation evidence, or interpretation guidance. Verify missing information in the cited manual, publication, or official source before use.
- Remote extraction offers OpenAI, Anthropic, AlpineAI SwissGPT, and generic OpenAI-compatible providers. Provider model lists can be queried without transmitting a PDF; remote PDF extraction remains opt-in and separately confirmed.
- AlpineAI follows its documented basic Chat Completions API; extraction JSON is validated locally because Structured Outputs compatibility is not documented.
- The library's **Katalog-Übersicht** dashboard summarizes the whole catalogue (instrument/item/language/topic counts) plus a per-language bar chart, a top-topics bar chart, and an item-text-coverage donut chart, all built from plain Flet controls with no charting dependency. See [gui_workspace.md](gui_workspace.md#catalog-overview-dashboard).
- A **Konstrukt-Ähnlichkeitsprüfung (semantisch)** panel below it embeds every instrument's name/constructs/description/keywords with a local sentence-transformers model (`all-MiniLM-L6-v2`) and lists candidate pairs whose embeddings are highly similar -- the "jingle-jangle" check: different instruments that may measure the same underlying construct. It never merges or flags anything automatically; a high score is a prompt for human review, not a finding. The first run downloads the model (~90 MB) and needs network access once; afterward it runs fully locally. See `src/core/nlp_engine.py`.
- The **Projekt und Auswahl** view shows a "Geschätzte Bearbeitungszeit der Batterie" panel for the currently selected versions/items: it sums each version's estimated completion time, preferring the catalog's curated `administration_time` text when it parses (for example "ca. 5-10 Minuten") and otherwise falling back to a clearly labelled, deliberately wide item-count heuristic keyed by response mode. A version with neither is shown as "unbekannt" rather than silently dropped or treated as zero. This is a planning aid for study design and ethics submissions, not a validated norm value -- see `src/core/battery_time_estimator.py`.

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

## Sync PDFs from Zotero

Set `ZOTERO_API_KEY` and `ZOTERO_USER_ID` (or `ZOTERO_LIBRARY_ID` for a group library) in the ignored local `.env`, optionally with `ZOTERO_LIBRARY_TYPE=group` and `ZOTERO_COLLECTION_KEY` to restrict the sync to one collection. Then run:

```powershell
python -m src.ingestion.zotero_source
```

This downloads new or changed `application/pdf` attachments into `data/questionnaires/inbox/`, tracking already-synced attachment versions in `data/questionnaires/review/zotero_sync_state.json` so repeat runs only fetch what changed. Each PDF gets a `<filename>.pdf.zotero-metadata.json` note with the source title, authors, DOI, and Zotero link, to speed up writing the rights sidecar below. Zotero metadata is never treated as a rights approval: a synced PDF still needs its own `<filename>.pdf.source.json` sidecar before `document_pipeline` will catalogue it, exactly as for a manually dropped PDF.

## Import New PDFs

Drop a PDF into `data/questionnaires/inbox/` (directly, or via the Zotero sync above), then process once or run the local watcher:

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

### R scoring syntax export

Choose `r_syntax` as the export format to get a base-R script (`.R`) implementing the version's documented scoring workflow: variable labels for every item, plus one score column per `ScoringAlgorithm`, assuming a data.frame named `df` with one column per item `variable_name` (for example imported from a REDCap/Qualtrics/CSV export using those exact names). It uses only base R, no `dplyr`/`sjlabelled`/`car` dependency.

Reverse-scored items (`is_reverse_scored: true`) are recoded automatically using the standard `(min + max) - value` reversal over that response set's own score range -- catalog response sets record each option's forward-direction score once and are shared by both forward- and reverse-keyed items (see the Rosenberg Self-Esteem Scale), so `ResponseOption.score` alone does not already encode reversal. The REDCap `calc`-field export (above) applies the identical reversal logic, so the two exporters cannot silently disagree on the same instrument's total. As with every other export, this is a translation of documented data, not a validated clinical scoring engine; verify results against the source publisher's manual before use in analysis.

### LimeSurvey TSV export/import (best-effort, not verified against a live LimeSurvey instance)

Choose `limesurvey_tsv` as the export format to get a LimeSurvey-importable tab-separated survey-structure file (`.txt`). Import a LimeSurvey TSV export the same way as a REDCap CSV, via **Dateien importieren**.

LimeSurvey's own manual describes this format incompletely: a fixed set of leading columns "followed by alphabetically-ordered database field names" whose exact set is genuinely version-dependent (2.x/3.x/4.x/5.x/6.x differ). Rather than guess at that version-dependent tail, this exporter/importer (`src/exporters/limesurvey_gen.py`) was built and verified directly against `TSVImportSurvey()` in LimeSurvey's own `application/helpers/admin/import_helper.php` (master branch, checked 2026-09-29): it only uses the fixed columns that function actually reads (`class`, `id`, `type/scale`, `name`, `relevance`, `text`, `help`, `language`, `validation`, `mandatory`, `other`, `default`, `assessment_value`), and that importer's own code tolerates any other missing/unknown column. A round-trip export→import against a real catalog entry (PHQ-9) was verified to preserve every item, response option, and score.

**This has not been verified against a live LimeSurvey instance** — unlike REDCap, which was checked against PyCap's real API. Test-import a generated file into a real or trial LimeSurvey installation before relying on it for an actual study.

- Supported LimeSurvey question types: `L` (List Radio) and `M` (Multiple choice) for categorical items, `N` (Numerical Input) for numeric items (a slider-typed item is exported as plain `N`; LimeSurvey's own slider widget is not produced), `S` (Short Free Text) for text items. Import notes any other LimeSurvey question type (e.g. `R` Ranking, `D` Date) by name in the instrument's `metadata.notes` instead of silently dropping it, exactly like the REDCap importer's handling of unsupported field types.
- Each item's `dimension` becomes a LimeSurvey group.
- `show_if` renders as a LimeSurvey ExpressionScript relevance equation (`q1 == "1" and q2 != "2"`); import parses a plain `and`-chain of `field == "value"`/`field != "value"` conditions back into `show_if` and preserves anything more complex (`or`, nested parentheses, an unresolvable field) verbatim in that item's notes rather than guessing, mirroring the REDCap branching-logic importer.
- Each `ResponseOption.score` becomes that answer's LimeSurvey `assessment_value` (rounded to the nearest integer, since LimeSurvey stores it as an int).

### Unipark paste-text export/import (best-effort, narrower scope than LimeSurvey)

Choose `unipark_txt` as the export format to get a plain-text file (`.unipark.txt`) meant to be pasted into Unipark's (EFS Survey / Tivian Discover XI) own "New question > Paste from Word" dialog, not opened as a file. Import a previously exported (or hand-written) Unipark paste-text file the same way as REDCap/LimeSurvey, via **Dateien importieren**; a `.txt` upload is auto-detected as LimeSurvey TSV or Unipark paste text by sniffing whether the first line looks like a LimeSurvey TSV header row (naming `class`/`name`/`text`).

Unipark does not publish its internal project export format (`.gpx`) at all -- it is closed-source, and unlike LimeSurvey there is no public source code to verify a full implementation against. Rather than guess at that undocumented format, this exporter/importer (`src/exporters/unipark_gen.py`) targets only the one Unipark import mechanism Tivian's own support documentation describes with a concrete, quotable example: pasting structured plain text to create several questions at once. Per that documentation (fetched 2026-09-29): each question is one text block separated by a blank line; each following line becomes one answer option, optionally with an explicit code using a semicolon (`1;Software`); a question with no answer lines becomes free text.

**This intentionally covers less than the LimeSurvey/REDCap exports**: no matrix/scale questions, no branching/filter logic, no Unipark internal question-type codes -- none of these are documented in enough verifiable detail to implement with confidence, and Tivian's own docs state the paste feature "cannot be used for all question types" without listing which. Always check the pasted result in Unipark's own editor before relying on it for a real study.

### Qualtrics QSF export/import (best-effort, not verified against a live Qualtrics import)

Choose `qualtrics_qsf` as the export format to get a Qualtrics-importable QSF file (`.qsf`, plain JSON). Import a QSF export the same way as a REDCap CSV, via **Dateien importieren**; the `.qsf` extension is unambiguous, so no content sniffing is needed.

Qualtrics does not publish a formal QSF schema. Rather than guess at its shape from memory, this exporter/importer (`src/exporters/qualtrics_gen.py`) was built and cross-checked against a real, publicly available `.qsf` file (the `egor` R package's Qualtrics template, fetched 2026-09-29): the `SurveyEntry`/`SurveyElements` split, the `"SQ"` question element shape (`PrimaryAttribute` as the question ID, `Payload` with `QuestionText`/`DataExportTag`/`QuestionType`/`Selector`/`Choices`/`ChoiceOrder`/`Validation`), and the `"BL"` block element shape all match that real file.

**This has not been verified against a live Qualtrics import** — like LimeSurvey (and unlike REDCap, which was checked against PyCap's real API). Test-import a generated file into a real or trial Qualtrics account before relying on it for an actual study.

- Supported Qualtrics question types: `MC` (Selector `SAVR` single choice, `MAVR` multiple choice) for categorical items, `TE` (Selector `SL`) for text items, and `TE` with `Validation.Settings.ContentType: "ValidNumber"` for numeric items. Any other Qualtrics question type (Matrix, Slider, Rank Order, ...) is noted by question ID/type in the instrument's `metadata.notes` instead of silently dropped, exactly like the REDCap/LimeSurvey importers.
- Each item's `dimension` becomes a Qualtrics block (`BL`).
- Choice codes are preserved through Qualtrics' own `RecodeValues` mechanism (the "recorded value" behind each sequential choice number), not through Qualtrics' separate and far less documented built-in scoring feature -- `ScoringAlgorithm` definitions stay external to the exported survey, exactly as they do for the LimeSurvey/Unipark exports.
- `show_if` branching is **not** translated into Qualtrics Display Logic: that JSON is deeply nested and not documented reliably enough to build with confidence. An exported question with branching conditions displays unconditionally.

### Reusable license profiles for institutionally licensed instruments

If your institution already holds a license for an instrument (for example through a physical or negotiated test library), save its recurring license details once as a named profile instead of retyping them for every PDF. Copy `data/questionnaires/license_profiles.example.json` to `data/questionnaires/review/license_profiles.json` (git-ignored) and fill in your institution's real agreements. Then generate a rights sidecar for one exact reviewed PDF:

```powershell
python -m src.ingestion.license_profiles --profile acme_library --pdf data/questionnaires/review/forms/mental_health/acme/<hash>_form.pdf --reviewed-by "Name, Testbibliothek" --content-reviewed
```

This fills in the license name/URL and permission basis from the profile and hashes the exact PDF, but it never sets `--content-reviewed`/`--study-metadata-reviewed` on your behalf: you still confirm those explicitly, per file, after checking the extracted content. The resulting sidecar is then approved exactly like a manually written one, with `--approve-draft`.

### License acknowledgment in the GUI

Instruments marked commercial (`is_commercial: true`) show a one-time confirmation dialog before their item wording is displayed or selected: name/URL of the license, and a checkbox confirming you have read and will follow its terms. This is a local, per-installation acknowledgment recorded in `data/psymetriq-settings.json`, not a redistribution approval; it is asked once per instrument, not on every view. Free, public-domain, or rights-unclear instruments are never gated. Metadata-only reference records (no item text stored) are also never gated, since there is no item wording to protect.

## Admin-only deployment configuration

Copy `data/admin_config.example.json` to `data/admin_config.json` (git-ignored, not exposed anywhere in the GUI) to control deployment-wide behavior for every user of a shared/cloud instance. It is read once at startup from disk; only whoever has server/file access to the deployment can change it.

```json
{
  "admin_config_schema_version": 1,
  "license_acknowledgment_enabled": true,
  "remote_processing_allowed": true,
  "hidden_views": [],
  "institutionally_licensed_instruments": [],
  "feature_flags": {}
}
```

- `license_acknowledgment_enabled`: set to `false` to skip the license-acknowledgment dialog entirely, for example while testing/debugging or for a small, trusted team. This does not change what the PDF intake pipeline treats as a rights-approved, redistributable document; that still requires the per-file rights sidecar described above.
- `remote_processing_allowed`: a deployment-wide kill switch for remote LLM PDF extraction. When `false`, remote extraction is unavailable for everyone regardless of each user's own settings, and the switch in **Einstellungen** is shown disabled.
- `hidden_views`: a list drawn from `catalog`, `project`, `exchange`, `intake`, `settings`. Any view named here disappears from the sidebar and cannot be navigated to, for every user. Use this to hide a menu item or an entire function (for example `intake`) from research colleagues on a shared deployment.
- `institutionally_licensed_instruments`: a list of `instrument_id` values (e.g. `["bdi_ii"]`) for which your institution has confirmed an actual license. Once listed here, every user sees that instrument's item text with no individual click-through -- only an operator with file access to this deployment can add to the list, never a regular user from within the app. It only controls who has to click an acknowledgment for item text that is *already* in the catalogue; it cannot make item text appear for an instrument that was never legitimately catalogued through the rights-gated PDF intake pipeline (see [Licensing workflow, Zotero sync, and admin configuration](admin_and_licensing.md)).
- `feature_flags`: a free-form `{"name": true/false}` map reserved for future ad-hoc toggles without needing a schema change.

Invalid admin config JSON falls back to all-enabled defaults and surfaces a startup warning; it never blocks the application from starting.

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

## REDCap: file export/import and the live API

### File-based exchange

Export a selected version as a REDCap Data Dictionary CSV from **Import & Export** (choose `redcap_csv` as the export format), then upload it in REDCap's own Online Designer under **Data Dictionary > Upload Data Dictionary**. To bring an existing REDCap project's Data Dictionary CSV into PsyMetriQ, use **Dateien importieren** and pick the `.csv` file directly; no live connection is required for either direction.

The exporter (`build_redcap_metadata_records` / `export_redcap_data_dictionary` in `src/exporters/data_exchange.py`) supports:

- `radio`/`dropdown`/`checkbox` for categorical items, with choices formatted as REDCap expects (`code, label | code, label`).
- `text` with `number` validation and min/max for numeric items, unless an item's `redcap_field_type` is `slider` (see below).
- `slider`, for a numeric item explicitly marked `redcap_field_type: "slider"`, with `numeric_minimum`/`numeric_maximum` rendered as the three-part REDCap slider label convention (`min, , max`).
- `calc` fields, one per `ScoringAlgorithm`, appended after the item fields. Each score's REDCap calc expression recodes reverse-scored or otherwise non-identity-coded items explicitly (nested `if([var]=code,score,...)`), so the calc field always reflects `ResponseOption.score`, never a raw REDCap choice code that happens to differ from it. A `sum`/`weighted` algorithm's `multiplier` is applied as `*multiplier`; a `mean` algorithm divides by the item count first.

The importer (`import_redcap_data_dictionary`) accepts `radio`/`dropdown`/`checkbox`/`text`/`notes`/`yesno`/`truefalse`/`slider` fields as respondent items (`yesno`/`truefalse` synthesize a two-option Yes/No or True/False response set; `slider` becomes a numeric item, defaulting to a 0-100 range when the dictionary specifies no min/max). Field types PsyMetriQ cannot represent as a respondent item -- `calc`, `descriptive`, `file`, `sql`, or anything unrecognized -- are **never silently dropped**: each is listed by field name and type in the imported instrument's `metadata.notes`, so you always know what didn't come across and why.

### Branching logic and matrix grouping

`ItemSchema` has three fields for these: `show_if` (a list of `BranchingCondition`, each an equality/inequality check against an earlier item's response, combined with AND -- empty means always shown), `matrix_group_name`, and `matrix_ranking`. This is intentionally a simple model: `show_if` can express `[field]='value' and [field2]<>'value2'`-style AND-chains, not arbitrary boolean logic (no OR, no nested groups).

- **Export** (`build_redcap_metadata_records`/`export_redcap_data_dictionary`): a `show_if` list renders as REDCap's branching-logic string, resolving each condition's `source_item_id` to that item's `variable_name`; `matrix_group_name`/`matrix_ranking` fill the corresponding Data Dictionary columns directly.
- **Import** (`import_redcap_data_dictionary`): a REDCap "Branching Logic" cell is parsed back into structured `show_if` conditions only when it is a plain AND-chain of `[field]='value'`/`[field]<>'value'` conditions referencing fields present in the same dictionary. Anything more complex (`or`, parentheses, an unresolvable field reference) is **not guessed at** -- the original text is preserved verbatim in that item's `metadata.notes` (prefixed "Original REDCap branching logic (not structurally parsed)") instead of being silently dropped or misrepresented. Matrix Group Name/Matrix Ranking columns are read directly.
- The GUI shows both, read-only, under each item in the version detail view ("Nur sichtbar, wenn ..." / "Matrixgruppe: ...") -- there is no branching-logic editor yet, only display of what a catalog entry (or REDCap import) already documents.

### Live REDCap API connection

Configure, in **Einstellungen > REDCap (Live-API)**: the project's API URL and the name of an environment variable (in your local `.env`, e.g. `REDCAP_API_TOKEN`) holding that project's API token. PsyMetriQ never stores the token itself in settings, projects, or exports -- only the environment variable's name, exactly like the LLM provider key settings.

In **Import & Export**:

1. **Mit REDCap verbinden** opens the connection and confirms the project's title/ID, so you know you are pointed at the right project before doing anything else.
2. **Erste ausgewählte Version pushen** takes the first version selected in your current project (the same one shown in the export preview), builds its REDCap fields, and pushes them -- but only after you confirm a dialog explaining exactly what will happen. This is deliberately careful: REDCap's Metadata Import API call replaces a project's **entire** data dictionary, not just the fields being sent. Before pushing, PsyMetriQ always fetches the project's current metadata and checks every new field name against it (case-insensitively); by default, any collision refuses the whole push outright and nothing is written, so a first push can only ever add fields, never silently overwrite or remove something already there.

   The confirmation dialog has an unchecked "Bestehende Felder mit gleichem Namen bewusst aktualisieren" checkbox for the deliberate opposite case: correcting or re-pushing an instrument you already pushed earlier. Ticking it before confirming passes `allow_update=True`, which replaces exactly the colliding fields' definitions with the newly built ones -- every other existing field, including ones from unrelated forms, is left untouched and kept in its original position. The result message reports how many of the pushed fields were newly added versus updated in place.
3. **Data Dictionary importieren** reads the connected project's entire data dictionary and adds it to the local catalogue as a new instrument, using the exact same parser as the file-based CSV import above (including the same "skipped fields go into the notes" behavior).

A REDCap API token grants full read/write access to its project; treat it like a password and never commit a real `.env` file.

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
