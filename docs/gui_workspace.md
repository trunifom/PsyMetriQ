# GUI Workspace

## Start

Install project dependencies, then launch the Flet desktop workspace from the repository root:

```powershell
python -m src.gui.main
```

For a browser session on the local machine:

```powershell
python -m src.gui.main --web --host 127.0.0.1 --port 8550
```

The default catalog is `data/questionnaires/json/`. The app does not require a database. Its five workspace areas are Bibliothek, Projekt, Import & Export, PDF-Posteingang, and Einstellungen.

## Library and item selection

Search locally by instrument/version names, language, constructs, item prompts, response labels, source citations, rights notes, and license names. The language filter accepts both language tags and locales: `de` matches German variants, while `de-AT` matches Austrian German even when the stored language is `de`. The separate Locale facet can further narrow that result. Age filters use broad groups (children 0-11, adolescents 12-17, adults 18-64, older adults 65+, and unknown) instead of source-specific population labels. Age ranges overlap intentionally: an instrument reported for ages 15-69 matches adolescent, adult, and older-adult filters. Other facets filter form type, commercial-use status, and exact license/documentation status. Rights are descriptive metadata, not an application-level use ban: all versions can be selected as project references. For item-bearing versions, choose whole versions, score scales, dimensions, or individual items; reference-only profiles store the selection as a metadata reference without item text. Details show source/reuse terms, source-reported scale length/dimensions, response choices, units, ranges, and scoring where available. Unknown rights remain explicitly unknown.

Psychometric metrics remain visible through version metadata where available; advanced metric-specific threshold filters are not yet exposed.

Reference-only records such as WHO-5, WEMWBS/SWEMWBS, GSE, and PSS remain searchable and selectable as project references. They show license/status, source links, source-reported length, and dimensions where known. Selecting or exporting a reference does not add item text; a reference-only ZIP entry is metadata JSON, not an empty questionnaire. The English Rosenberg Self-Esteem Scale is bundled under the University of Maryland's public-domain notice.

## Projects and process history

Projects use versioned `.psymetriq.json` files. They store:

- Project name, description, catalogue path, and generated project ID.
- Stable instrument/version IDs and optionally selected item IDs; catalogued item text is referenced, not duplicated into the project.
- Optional study-specific wording and a required reason, kept separate from catalogue source text.
- A bounded list of timestamps and summaries for import, selection, settings, and export actions.

Use Projekt > Projekt speichern or Projekt laden to continue later or move the workflow between workstations. Projects with unresolved version references remain loadable and are marked as unresolved. No participant data or API key values belong in projects.

## Import and export

Supported imports:

- PsyMetriQ family JSON, validated against the domain schema.
- HL7 FHIR R4 `Questionnaire` JSON, converted to a rights-unassessed family.
- REDCap Data Dictionary CSV; the default language for this source is set in Einstellungen.

An import never silently replaces a version. New versions merge only when family identity matches and version IDs do not collide; malformed or conflicting families are rejected. FHIR supports standard question/choice fields plus documented PsyMetriQ extensions for item dimensions, response modes, response-set IDs, variable names, integer response codes, scores, units, and version display names. Unsupported source metadata may not survive normalization; retain and archive the original source file when exact preservation is required.

Supported exports for selected versions/items:

- **PsyMetriQ JSON:** canonical portable family JSON.
- **FHIR R4 Questionnaire JSON:** interoperable questionnaire definition.
- **XLSX workbook:** separate Items, Antwortoptionen, Scoring, and Quellen sheets for review and study setup.
- **REDCap Data Dictionary CSV:** field names, labels, response choices, validation bounds, section headers, and requiredness.
- **Item CSV:** review-friendly item records and response sets.

Multi-version project exports are packaged as a ZIP with a `manifest.json`. Export previews show the first selected version. Reference-only selections create `*.reference.json` metadata entries with a clear no-item-text notice; item-bearing selections use the chosen exchange format. The app does not upload a project to REDCap, administer a questionnaire, collect responses, export R syntax, or generate CDISC ODM/DDI yet.

XLSX is an export/review workbook, not an import format. Unipark is not yet supported because a stable, versioned vendor import contract has not been specified; do not assume a generic CSV is directly importable there.

REDCap choice codes are not treated as psychometric scores. FHIR/REDCap imports set rights to unknown unless a separately reviewed rights record is provided. Check instrument licenses, translations, response options, and scoring before field use.

Select an entire scoring scale from the version-detail panel or assemble selections item by item/by dimension, including a single documented dimension. Use **Anpassen** on an item to record study-specific wording and a required rationale. The source JSON is never changed. Adapted wording is clearly marked, included in the project export, and causes any score using that item to be omitted. A wording change can affect licensing and validity; review permissions, pretest, and revalidate independently before field use. A license status never disables study adaptation controls; the software records the terms so researchers can decide whether a specific activity is covered.

## Settings and portability

The GUI writes machine-local settings to `data/psymetriq-settings.json`, which is excluded from Git. The settings file can also be imported or exported as JSON. It contains:

- Catalog and export directories.
- PDF inbox/review folders and OCR languages/enablement.
- PDF size, page and extracted-text limits; minimum text; confidence threshold; watcher interval.
- Default language and export format.
- LLM provider/model and an OpenAI-compatible endpoint URL.
- The *name* of the environment variable containing a provider key, never its value.
- An opt-in flag for remote PDF processing, disabled by default.

Settings can be edited directly in JSON or in the Settings screen. The provider key itself must remain in the environment or an institution-approved secret manager. The GUI asks for a second confirmation each time a PDF run would send extracted text to a remote LLM.

Provider choices are OpenAI, Anthropic, AlpineAI SwissGPT, and a generic OpenAI-compatible endpoint. `Modelle laden` asks the selected provider account for available model IDs (OpenAI/AlpineAI/compatible `GET <base>/models`; Anthropic `GET https://api.anthropic.com/v1/models`). Availability is account- and permission-specific; the model field remains editable for aliases or IDs omitted from discovery. Listing models sends an authenticated metadata request, not PDF text.

For a blank/gray UI, start with `--log-level DEBUG`. GUI logs report session start, catalog family/version counts, visible-version counts, safe version IDs, and render exceptions; item wording, PDF text, and API-key values are not logged. The catalog's version list is bounded to its viewport and scrolls independently; a positive `visible_versions` count with a gray canvas indicates a client-side layout/render issue rather than a missing catalog.

AlpineAI SwissGPT follows the supplied API documentation: base URL `https://api.prod.alpineai.ch/v1`, Bearer API-key authentication, `POST /chat/completions`, and `GET /models`. Set `ALPINEAI_API_KEY`; optional `ALPINEAI_BASE_URL` and `ALPINEAI_MODEL` configure CLI defaults. The example model `mistral-large-3-675b-nvfp4` comes from AlpineAI's documentation; use the live model list to select the models your account actually exposes. The legacy `SWISSGPT_API_KEY` is accepted as a fallback.

AlpineAI's documentation confirms basic chat completions, but does not establish OpenAI Structured Outputs compatibility. PsyMetriQ therefore sends the extraction schema as prompt text and validates returned JSON locally with Pydantic; malformed or truncated responses are rejected. This workflow does not use streaming, tools, prompt-based Llama tool calls, file upload, or extended-thinking fields. OpenAI uses Structured Outputs; Anthropic uses its native Messages API with schema-prompted JSON and local validation. Remote PDF content is still off by default and requires per-run confirmation.

## Help and limitations

Information buttons beside controls open an explanation and a concrete example. Search inputs, filters, version rows, and selection controls have descriptive accessible labels. The catalog list is bounded and scrolls independently from filters/details. Tooltips also name icon-only controls. Help text does not replace licensing, psychometric, or institutional review.

Settings are local preferences; project files are explicit user-controlled snapshots. Both use schema version `1` and atomic JSON persistence. The current GUI is a usable first workspace, not yet the final workflow builder. Missing areas include database-source federated search, drag/reorder composition, custom workflow automation, diff/merge between project revisions, live REDCap API integration, R/ODM/DDI outputs, and a complete schema editor. Project history is not an immutable regulated audit trail.
