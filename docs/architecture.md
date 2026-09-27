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
- `src/ingestion/`: source adapters for Zotero, PDF parsing, and structured LLM extraction.
- `src/exporters/`: translations from domain objects to external formats and remote systems.
- `src/gui/viewmodels/`: UI-facing state and commands, including the assembled-item collection.
- `src/gui/views/`: Flet presentation components; no direct SQL or secret management.
- `tests/unit/`: deterministic tests of model, service, and view-model behavior.
- `tests/integration/`: tests spanning adapters, storage, or external-system boundaries with controlled fixtures.
- `data/`: local working data. Only the explicitly named synthetic demo JSON fixtures are Git-allowlisted; real PDFs, extracted content, and exports are excluded by default.
- `docs/`: user, architecture, security, coding, and testing documentation.

## File-backed search and team sharing

Questionnaire JSON files are the portable source of shared content. `QuestionnaireSearchEngine` reads the files directly, validates each with the Pydantic models, and keeps the validated objects in memory for local search. It creates no database and does not modify source files. Call `reload()` after the shared folder changes; a failed reload preserves the last valid in-memory view.

Use an access-controlled synchronized folder for private team data. Only synthetic fixtures or content explicitly approved for public distribution belong in this repository. The search service does not provide file locking or conflict resolution; teams should coordinate simultaneous edits through their file-sharing system.

## Implementation status and asynchronous boundaries

The current implementation includes Phase 1 (schema and synthetic fixture generator) and Phase 2 (file-backed search). Flet state/rendering, embedding computation, REDCap export, and LLM/PDF ingestion remain planned until implemented and tested.

When GUI and integration capabilities are added, network requests and expensive CPU work must not block Flet's event loop. Use async APIs where available and offload synchronous file or model work to an appropriate worker boundary. Cancellation, timeouts, and failure reporting must be designed at the owning service boundary. Do not make Pydantic models depend on those runtime frameworks.
