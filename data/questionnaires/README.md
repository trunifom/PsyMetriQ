# Questionnaire Test Data

This directory contains versioned questionnaire JSON files for application tests and a small set of original forms whose source explicitly permits redistribution. These records contain real questionnaire item wording; they are not synthetic mock data.

## Contents

| File | Instrument/version | Language and locale | Permission status |
| --- | --- | --- | --- |
| `pdfs/phq9_en.pdf` | PHQ-9 English source form | English, `en-US` | Official PHQ Screeners site permits reproduction and distribution |
| `pdfs/phq9_de_de.pdf` | PHQ-9 German for Germany | German, `de-DE` | Official PHQ Screeners site permits reproduction and distribution |
| `pdfs/gad7_en.pdf` | GAD-7 English source form | English, `en-US` | Official PHQ Screeners site permits reproduction and distribution |
| `pdfs/gad7_de_at.pdf` | GAD-7 German for Austria | German, `de-AT` | Official PHQ Screeners site permits reproduction and distribution |
| `pdfs/gad7_de_ch.pdf` | GAD-7 German for Switzerland | German, `de-CH` | Official PHQ Screeners site permits reproduction and distribution |
| `json/phq9.json` | PHQ-9 family with English and Germany-German forms | `en-US`, `de-DE` | Pydantic-validated; links each form to its permitted PDF and checksum |
| `json/gad7.json` | GAD-7 family with English, Austrian-German, and Swiss-German forms | `en-US`, `de-AT`, `de-CH` | Pydantic-validated; links each form to its permitted PDF and checksum |

The regional German forms are separate version records. Do not silently merge or normalize their language-specific wording and response labels.

## Official source and permission

Source: [PHQ Screeners, Select a Screener](https://www.phqscreeners.com/select-screener). The official page states: “All PHQ, GAD-7 screeners and translations are downloadable from this website and no permission is required to reproduce, translate, display or distribute them.” The downloaded forms also contain a reproduction notice. Source URLs, access date, redistribution statement, and PDF SHA-256 digest are recorded in the corresponding JSON `source_documents` entries.

The validation-study articles are linked by DOI only. Their PDFs are not bundled because redistribution permission for those articles was not established. Citations identify the evidence source; they do not imply that every translation has independent validation evidence.

## Regenerate the JSON catalogue

The PDFs are committed source assets. The builder does not download or overwrite them:

```powershell
python data/questionnaires/build_catalog.py
```

It validates all item/response/scoring references, checks that each referenced PDF exists, recalculates its SHA-256 digest, and writes `json/phq9.json` and `json/gad7.json`. To run only these data-integrity tests:

```powershell
pytest tests/unit/test_instrument_catalog.py -q
```

## Scoring and use limitations

- PHQ-9 contains nine scored symptom items. Its functional-impact follow-up question is represented as an unscored item with its own response scale.
- GAD-7 contains seven scored items.
- The JSON contains score mappings and source descriptions, not a complete interpretation/manual or diagnostic workflow.
- PHQ-9 item 9 concerns thoughts of death or self-harm and is tagged `suicide-related-thoughts` for downstream interface handling. This metadata is not a risk assessment or response protocol. Any real-world administration requires an independently reviewed clinical workflow and local support/escalation procedures.
- The PHQ/GAD forms are screening instruments. They do not alone establish a diagnosis or replace professional assessment.
- Original-language and translated forms can differ in typography, punctuation, or wording. Use the bundled PDF as the source of truth for the exact form; JSON is a structured representation for software testing.
- Adult/general clinical applicability is not inferred for translated variants unless a version-specific source establishes it. The English source validation population is recorded as study context, not as an eligibility rule.

## Adding another instrument

1. Identify the exact edition, language, locale, population, and source publication.
2. Verify item-text and PDF redistribution permission for the intended public repository. Record a URL to the permission statement or a written permission reference.
3. If rights are unclear, add a citation/official link to `docs/instrument_library.md`; do not copy the PDF or item text.
4. Add the source PDF only when redistribution is explicitly permitted. Record the exact source URL, permission basis, retrieval date, and SHA-256 checksum.
5. Create one `QuestionnaireVersion` per language/locale/form. Preserve source wording, response scales, unscored questions, scoring targets, population evidence, and version lineage.
6. Add validation tests for item counts, response labels, scoring exclusions, locales, provenance, search, and filters.

Do not store participant-level responses, patient records, private research papers, licensed scales, authentication data, or API credentials in this directory.
