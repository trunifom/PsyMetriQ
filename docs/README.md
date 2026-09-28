# PsyMetriQ Documentation

This directory is the maintained home for project documentation. Start here, then use the document that matches the task you are working on.

## Documents

- [Software overview](software_overview.md): project goals, current capabilities, planned capabilities, and the responsibilities of the main modules.
- [Architecture](architecture.md): layer boundaries, data flow, model relationships, and implementation status.
- [Domain data model](domain_data_model.md): instrument families, language/form/population variants, contributor roles, and provenance links.
- [User manual](user_manual.md): setup and currently supported commands, including generation of synthetic questionnaire fixtures.
- [Instrument library](instrument_library.md): curated known instruments, validation/population notes, authoritative sources, and redistribution status.
- [PDF intake and extraction](pdf_intake.md): local inbox, OCR/LLM options, review drafts, and rights-gated promotion.
- [External source search](external_sources.md): public NIH CDE, NLM LOINC, and PubMed connectors, previews, and rights boundaries.
- [GUI workspace](gui_workspace.md): catalogue workflow, project/settings persistence, formats, help dialogs, and limitations.
- [Coding guidelines](coding_guidelines.md): typing, documentation, validation, asynchronous work, logging, testing, and commit conventions.
- [Security](security.md): credential handling, protected data, Git safeguards, and incident response.
- [Testing](testing.md): test scope, local commands, and expectations for adding coverage.

## Documentation policy

Documentation must distinguish implemented behavior from planned behavior. Update the relevant pages whenever a public model, command, module responsibility, security control, or user workflow changes. Keep examples synthetic and never use confidential participant information or licensed questionnaire item text unless its use and distribution have been explicitly cleared.
