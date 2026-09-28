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

Search locally by instrument/version names, language, constructs, item prompts, or response labels. Filter concrete versions by language, locale, form type, target population, and recorded commercial-use status. Selecting a version adds the whole version to the project; checking individual items narrows the project's export selection. The details pane shows source/right statements, scoring definitions, response choices, units, and numeric ranges when present. Absence of a rights statement is displayed as unknown, not as permission.

Psychometric metrics remain visible through version metadata where available; advanced metric-specific threshold filters are not yet exposed.

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

Multi-version project exports are packaged as a ZIP with a `manifest.json`. Export previews show the first selected version. The app creates definitions only; it does not upload a project to REDCap, administer a questionnaire, collect responses, export R syntax, or generate CDISC ODM/DDI yet.

XLSX is an export/review workbook, not an import format. Unipark is not yet supported because a stable, versioned vendor import contract has not been specified; do not assume a generic CSV is directly importable there.

REDCap choice codes are not treated as psychometric scores. FHIR/REDCap imports set rights to unknown unless a separately reviewed rights record is provided. Check instrument licenses, translations, response options, and scoring before field use.

Select an entire scoring scale from the version-detail panel or assemble selections item by item/by dimension. Use **Anpassen** on an item to record study-specific wording and a required rationale. The source JSON is never changed. Adapted wording is clearly marked, included in the project export, and causes any score using that item to be omitted. A wording change can affect licensing and validity; review permissions, pretest, and revalidate independently before field use.

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

For Alpine AI / SwissGPT, choose `OpenAI-kompatibler Endpoint` only after Alpine supplies the authorized base URL, model ID, key, and confirms OpenAI Chat Completions/Structured Outputs compatibility. No SwissGPT endpoint is hard-coded. Anthropic uses its native Messages API. OpenAI and compatible endpoints use Structured Outputs; Claude returns schema-prompted JSON that PsyMetriQ validates locally because the extraction schema exceeds Anthropic's current strict-output optional-field limit.

## Help and limitations

Information buttons beside controls open an explanation and a concrete example. Search inputs, filters, version rows, and selection controls have descriptive accessible labels. Tooltips also name icon-only controls. Help text does not replace licensing, psychometric, or institutional review.

Settings are local preferences; project files are explicit user-controlled snapshots. Both use schema version `1` and atomic JSON persistence. The current GUI is a usable first workspace, not yet the final workflow builder. Missing areas include database-source federated search, drag/reorder composition, custom workflow automation, diff/merge between project revisions, live REDCap API integration, R/ODM/DDI outputs, and a complete schema editor. Project history is not an immutable regulated audit trail.
