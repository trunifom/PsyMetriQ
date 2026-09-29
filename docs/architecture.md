# Architecture

## Architectural intent

PsyMetriQ follows a small-core, layered design with MVVM at the user-interface boundary. The Pydantic schema is the source of truth for domain data. Business logic consumes validated models and must not depend on Flet controls. Views render state and dispatch user intent; they must not contain SQL or persistence rules.

The data flow is intended to be:

1. Ingestion adapters extract source content and construct validated questionnaire models.
2. Domain validation rejects malformed objects and unresolved references.
3. The file-backed search service reads validated JSON into memory for local discovery.
4. View models maintain the selected-item assembly state.
5. Domain services calculate similarity or prepare exports without reaching into UI controls.
6. Export adapters translate validated data to external formats and report remote errors.

Pydantic models cross module boundaries. Dictionaries may appear as an explicit serialization format at JSON/API boundaries or as values inside a model (for example COSMIN metrics); they are not substitutes for validated domain objects in internal interfaces.

## Current domain model

`QuestionnaireParent` represents a conceptual instrument family and owns one or more concrete `QuestionnaireVersion` objects. A concrete version can represent a full or short form, revision, translation, cultural or population adaptation, or a combination of these. Version metadata keeps language separate from regional locale and can record target populations, credited contributors by role, source citations, and the version(s) it was based on. See the [domain data model](domain_data_model.md) for the complete meaning and examples.

A version owns its response sets, items, and scoring algorithms. Each `ItemSchema` references one response set by key; each scoring algorithm references item IDs from its containing version. Validators enforce these local relationships at construction time. Instrument-level authorship is distinct from the translators, adaptors, and validators credited on a particular version.

`variable_name` follows the current project convention: it starts with an ASCII letter, contains only ASCII letters, digits, or underscores, and is no longer than 26 characters. Names are compared case-insensitively for uniqueness within a version. Changing this convention requires updating validators, tests, and documentation together.

For version lineage, references to versions inside the same instrument family are checked for existence and cycles. References to another `instrument_id` can be recorded, but their existence is not yet globally verified across separate files.

## Repository boundaries

- `schemas/`: domain data contracts and validation; no GUI, SQL, network, or REDCap concerns.
- `src/core/`: business services such as file-backed search and NLP, independent of view widgets.
- `src/core/external_sources.py`: read-only NIH CDE, NLM LOINC, and PubMed connectors; returned candidates are not persisted or rights-approved.
- `src/ingestion/`: local PDF intake/OCR, structured extraction adapters, and a Zotero attachment sync that stages PDFs into the inbox.
- `src/ingestion/provider_models.py`: account-scoped, metadata-only provider model discovery; API-key values remain in environment variables.
- `src/exporters/`: translations from domain objects to external formats and remote systems.
- `src/gui/application.py`: Flet workspace for catalogue search, item/version assembly, import/export, PDF intake, and settings.
- `src/gui/catalog_store.py` and `src/gui/workspace.py`: validated catalog updates, conflict handling, versioned user settings, project snapshots, and workflow steps.
- `src/gui/views/` and `src/gui/viewmodels/`: reserved for further decomposition as the workspace grows.
- `tests/unit/`: deterministic tests of model, service, and view-model behavior.
- `tests/integration/`: tests spanning adapters, storage, or external-system boundaries with controlled fixtures.
- `data/`: local working data. Only the explicitly named synthetic demo JSON fixtures are Git-allowlisted; real PDFs, extracted content, and exports are excluded by default.
- `docs/`: user, architecture, security, coding, and testing documentation.

## File-backed search and team sharing

Questionnaire JSON files are the portable source of shared content. `QuestionnaireSearchEngine` reads the files directly, validates each with the Pydantic models, and keeps the validated objects in memory for local search. It creates no database and does not modify source files. Call `reload()` after the shared folder changes; a failed reload preserves the last valid in-memory view.

Use an access-controlled synchronized folder for private team data. Only synthetic fixtures or content explicitly approved for public distribution belong in this repository. The search service does not provide file locking or conflict resolution; teams should coordinate simultaneous edits through their file-sharing system.

## Implementation status and asynchronous boundaries

The current implementation includes Phase 1 (schema and synthetic fixture generator), Phase 2 (file-backed search), and a guarded PDF-intake vertical slice. The importer extracts text/metadata locally, can attempt OCR, and routes Pydantic-structured LLM drafts only after explicit cloud-processing opt-in. It promotes a form only after human item review, a rights sidecar bound to the exact PDF SHA-256, one concrete version per source PDF, complete non-truncated extraction, high confidence, and schema validation. A separate validation-study reference path requires reviewed citation metadata and explicit PDF redistribution rights. Unknown rights, manuals/mixed documents, incomplete forms, and low-confidence/scanned documents stay in the ignored review area. This is a guarded document-ingestion foundation, not a guarantee that arbitrary new PDFs can be interpreted perfectly without review.

Catalogue search/selection, project persistence, settings, standard-format exchange, and PDF intake are available in Flet. `src/ingestion/license_profiles.py` lets a reviewer save recurring, institution-specific license boilerplate (name, URL, permission basis) once and reuse it to fill in a rights sidecar for a new PDF; it still hashes the exact file and requires an explicit, per-file `--content-reviewed`/`--study-metadata-reviewed` flag, so a profile speeds up repetitive typing without weakening the human review gate. Separately, the GUI asks for a one-time, per-instrument, local license acknowledgment (checkbox + license name/URL) before showing or selecting item wording for any `is_commercial: true` instrument; this is a local usage confirmation stored in settings, not a redistribution approval, and it never applies to free/unclear instruments or to metadata-only reference records. `src/gui/admin_config.py` reads a separate, git-ignored `data/admin_config.json` once at startup for deployment-wide operator toggles that are not exposed in the GUI: disabling the license-acknowledgment dialog outright (test/debug or a trusted single-admin deployment), a kill switch for remote LLM processing, hiding named sidebar views for every user, and a free-form flag map reserved for future gating. None of these toggles change what the intake pipeline treats as a rights-approved, redistributable document. `src/exporters/redcap_api.py` adds a live REDCap connection on top of the existing file-based REDCap Data Dictionary CSV exchange: it can push a version's fields into a connected project (always merging with, and refusing on any collision against, that project's current metadata, since REDCap's Metadata Import API replaces the whole data dictionary) and pull a project's entire data dictionary into the local catalogue, reusing the same CSV parser as a manual file import. `src/exporters/data_exchange.py`'s REDCap export/import now also covers `slider` fields (including deriving their min/max labels), emits one REDCap `calc` field per `ScoringAlgorithm` with an explicit, reverse-scoring-aware recoding expression rather than assuming a raw field value equals its score, and never silently drops an unsupported REDCap field type (`calc`/`descriptive`/`file`/`sql`/unrecognized) on import -- each is listed in the imported instrument's metadata notes instead. `src/ingestion/zotero_source.py` incrementally stages `application/pdf` attachments from a configured Zotero library (or one collection) into the local inbox, tracking Zotero library versions so repeat runs only fetch new/changed files; it writes a plain metadata note (title, authors, DOI, Zotero link) beside each PDF for reviewer convenience but never creates a rights sidecar, so downloaded PDFs still require the same human rights review as any other inbox file before the intake pipeline can publish them. Federated database search, embedding-based redundancy checks, LimeSurvey exchange, branching logic/matrix-group modeling, and R syntax export remain planned.

The PDF pipeline offloads blocking file/PyMuPDF operations to a worker thread and uses async clients for optional LLM calls. GUI catalogue reads, imports, persistence, and PDF processing likewise run in worker threads where appropriate; event handlers must not block Flet's event loop. Domain models remain independent of Flet and runtime frameworks.
