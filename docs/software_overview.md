# PsyMetriQ Software Overview

## Purpose

PsyMetriQ is an open-source project intended to help researchers assemble psychometric questionnaires from structured, validated data. Its planned workflow connects questionnaire ingestion, local search, semantic redundancy checks, an interactive assembly canvas, and research-platform exports. The project is designed for psychology, health sciences, and data-science workflows where provenance, validation, and safe handling of research data matter.

The architecture document `psymetriq_readme.md` is the original product and module brief. This documentation describes the code as it exists and labels roadmap behavior as planned; a design brief is not evidence that a feature is already operational.

## Current implementation status

Phase 1 provides the Pydantic source-of-truth models in `schemas/questionnaire_schema.py`, model-level validation, a synthetic fixture generator in `data/generate_mock_data.py`, and unit tests in `tests/unit/test_schema.py`. The generator writes two synthetic examples to `data/02_extracted_jsons/`.

The database/search engine, Flet workflow, NLP similarity checks, REDCap exporter, and LLM/PDF ingestion are roadmap capabilities. Their source directories are present, but this overview does not claim that they are complete or production-ready.

## Main capabilities and responsibilities

- **Questionnaire schema:** represents instruments, versions, items, response options, and scoring algorithms. It validates local identifiers and references before data can be passed to other layers.
- **Synthetic data generator:** creates development fixtures using fabricated text. These are not validated clinical instruments and must never be used to assess people.
- **Search engine (planned):** load validated questionnaire content into DuckDB and search item text, dimensions, and instrument metadata.
- **Assembly GUI (planned):** provide search, a questionnaire canvas, and an inspector through Flet, with view state isolated from persistence and SQL.
- **Redundancy analysis (planned):** calculate semantic similarity between candidate items and items already selected, and surface review warnings rather than making clinical decisions.
- **Export and ingestion (planned):** map validated models to REDCap metadata or R syntax, and extract source material through configured APIs and PDF parsing.

## Phase-1 public model and function reference

- `ResponseOption`: response code, human-readable label, and scoring value.
- `ItemSchema`: item identity, REDCap field name, construct dimension, prompt, response-set reference, reverse-scoring flag, and field type. `validate_variable_name` enforces the project’s REDCap-compatible naming rule.
- `ScoringAlgorithm`: scoring method, target item IDs, output name, and missing-data note.
- `QuestionnaireVersion`: language, response sets, items, and scoring metadata. `validate_references` ensures item IDs and case-insensitive variable names are unique, every response-set reference exists, and every scoring target names an item in this version.
- `QuestionnaireParent`: stable instrument metadata and one or more versions. `validate_version_ids` prevents duplicate version IDs within an instrument.
- `build_demo_questionnaire`: constructs a validated model from synthetic specifications.
- `generate_mock_data`: writes the two JSON fixtures and returns their paths. An optional output directory supports isolated tests. Filesystem errors are logged and re-raised.

See the [user manual](user_manual.md) for commands and the [architecture](architecture.md) for how these responsibilities fit together.
