# PsyMetriQ Software Overview

## Purpose

PsyMetriQ is an open-source project intended to help researchers assemble psychometric questionnaires from structured, validated data. Its planned workflow connects questionnaire ingestion, local search, semantic redundancy checks, an interactive assembly canvas, and research-platform exports. The project is designed for psychology, health sciences, and data-science workflows where provenance, validation, and safe handling of research data matter.

The architecture document `psymetriq_readme.md` is the original product and module brief. This documentation describes the code as it exists and labels roadmap behavior as planned; a design brief is not evidence that a feature is already operational.

## Current implementation status

Phase 1 provides the Pydantic source-of-truth models in `schemas/questionnaire_schema.py`, model-level validation, a synthetic fixture generator in `data/generate_mock_data.py`, and unit tests in `tests/unit/test_schema.py`. Phase 2 provides file-backed search in `src/core/search_engine.py`. Rights-reviewed real PHQ-9, GAD-7, DASS-21, DASS-Y, and IPAQ forms and JSON families are maintained under `data/questionnaires/`, separate from the synthetic demo fixtures.

The file-backed search service, guarded PDF intake/review pipeline, and Flet workspace are implemented. NLP similarity checks, Zotero sync, live REDCap API, and R syntax exporters remain roadmap capabilities and are not claimed to be production-ready.

## Main capabilities and responsibilities

- **Questionnaire schema:** represents instrument families and concrete versions, including form, language, locale, audience, contributor roles, source citations, lineage, items, response options, and scoring algorithms. It validates local identifiers and references before data can be passed to other layers.
- **Synthetic data generator:** creates development fixtures using fabricated text. These are not validated clinical instruments and must never be used to assess people.
- **Real instrument test corpus:** provides permission-reviewed PHQ-9, GAD-7, DASS-21, DASS-Y, IPAQ, and public-domain Rosenberg records. WHO-5 and WEMWBS are searchable link-only profiles with no item wording. Forms flagged as translation-quality-uncertain are not automatically interchangeable validated editions.
- **PDF intake/review:** routes new PDFs into private drafts, optionally extracts a Pydantic candidate with OpenAI, Anthropic, AlpineAI SwissGPT, or another OpenAI-compatible LLM endpoint, and requires human, checksum-bound item/license review before cataloguing a questionnaire form. Licensed validation papers use a separate citation-reviewed reference catalog.
- **File-backed search engine:** validate portable JSON files against the Pydantic models, keep an in-memory view, and search item text, dimensions, response labels, version metadata, constructs, and instrument metadata. It creates no database and can read a synchronized team folder.
- **Public source connectors:** read-only NIH CDE question/answer previews, NLM LOINC display terms, and PubMed citations are available from Python/CLI. Results are ephemeral suggestions with rights marked unassessed; external federated search is not yet in the GUI.
- **Flet workspace:** faceted local catalogue search, version/rights/item/response inspection, whole-scale or individual-item selection, reasoned study-specific wording adaptations, versioned projects/settings, JSON/FHIR/REDCap CSV imports, and ZIP exports including XLSX, plus guarded PDF intake with explicit remote-processing confirmation.
- **Provider/model selection:** fetches account-visible OpenAI, Anthropic, AlpineAI, or compatible model IDs from provider model-list APIs; model IDs remain editable, and API-key values are not saved. AlpineAI uses documented Chat Completions and locally validates prompted JSON rather than assuming Structured Outputs support.
- **Provider model service:** `src/ingestion/provider_models.py` lists account-available models through OpenAI-compatible `/models` routes and Anthropic's native `/v1/models` API. It performs metadata-only requests; model IDs can also be entered manually.
- **Redundancy analysis (planned):** calculate semantic similarity between candidate items and items already selected, and surface review warnings rather than making clinical decisions.
- **Export and ingestion:** file exchange supports PsyMetriQ JSON, FHIR R4 Questionnaire JSON, XLSX review workbooks, REDCap Data Dictionary CSV, and item CSV. XLSX is export-only; Unipark import/export, full REDCap API upload, R syntax, CDISC ODM, DDI, and GUI federated-source search remain planned.

## Phase-1 public model and function reference

- `ResponseOption`: response code, human-readable label, and scoring value.
- `ItemSchema`: item identity, REDCap field name, construct dimension, prompt, response-set reference, reverse-scoring flag, and field type. `validate_variable_name` enforces the project’s REDCap-compatible naming rule.
- `ScoringAlgorithm`: scoring method, target item IDs, output name, and missing-data note.
- `QuestionnaireVersion`: language, response sets, items, and scoring metadata. `validate_references` ensures item IDs and case-insensitive variable names are unique, every response-set reference exists, and every scoring target names an item in this version.
- `QuestionnaireParent`: stable instrument metadata and one or more versions. `validate_version_ids` prevents duplicate version IDs within an instrument.
- `QuestionnaireContributor`: records instrument authorship or version-specific author, translator, adapter, editor, reviewer, or validator credit.
- `TargetPopulation`: records a source-reported population label and optional age bounds.
- `QuestionnaireVersionReference`: connects a derived version to a source instrument/version.
- `QuestionnaireSourceDocument`: records exact source URLs, local approved PDF paths, redistribution basis, retrieval dates, and checksums.
- `ItemSchema.is_scored`: distinguishes score-bearing items from supplementary questions such as the PHQ-9 functional-impact follow-up.
- `QuestionnaireVersion`: differentiates `language` from `locale`, classifies full/short/long/screening forms, and supports multiple simultaneous variant types.
- `MeSHTerm` and `QuestionnaireMetadata`: preserve curated keywords, aliases, controlled MeSH descriptors, characteristics, and review notes at instrument, version, or item scope.
- `QuestionnaireSearchFilters`: combines exact-match catalogue facets; alternative values within a facet use OR, while different facets use AND. Free-text search can be combined with these filters.
- `data/questionnaires/build_catalog.py`: rebuilds the permission-cleared PHQ-9/GAD-7 family JSON from the committed PDFs and records their SHA-256 hashes.
- `data/questionnaires/build_dass_catalog.py`: rebuilds separate adult DASS-21 and youth DASS-Y families, preserving their different age ranges, multipliers, and translation caveats.
- `data/questionnaires/build_ipaq_catalog.py`: rebuilds English/German adult IPAQ and English IPAQ-E records with numeric duration units rather than fabricated categorical scales.
- `src/ingestion/document_pipeline.py`: processes local PDFs, extracts text and metadata, optionally requests a structured draft after cloud opt-in, and routes unapproved or incomplete input to review.
- `src/ingestion/llm_extractor.py`: defines the typed, provisional extraction draft and OpenAI, Anthropic, and AlpineAI adapters; provider responses are validated locally and none makes rights or validity decisions.
- `build_demo_questionnaire`: constructs a validated model from synthetic specifications.
- `generate_mock_data`: writes the two JSON fixtures and returns their paths. An optional output directory supports isolated tests. Filesystem errors are logged and re-raised.

See the [user manual](user_manual.md) for commands and the [architecture](architecture.md) for how these responsibilities fit together.

## Phase-2 search API

- `QuestionnaireSearchEngine(data_directory)`: validates `*.json` files from a local or synchronized directory into an in-memory search view.
- `reload()`: replaces the in-memory view only after every file validates; returns the number of loaded instruments and leaves the previous state unchanged on failure.
- `search_items(keyword)`: returns typed `QuestionnaireSearchResult` models for instrument, version, dimension, item, and response-label matches. A blank query returns no results.
- `QuestionnaireDataError`: signals unreadable, invalid, or duplicate instrument files. Failures are logged; source JSON is never edited by the search service.
