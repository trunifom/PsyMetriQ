# Questionnaire Test Data

This is a portable, database-free library of questionnaire-family JSON records and source forms with documented redistribution rights. It contains real item wording for PHQ-9, GAD-7, DASS-21, DASS-Y, and IPAQ variants. These are research and software test fixtures, not diagnostic software or clinical response procedures.

## Directory Layout

```text
data/questionnaires/
|-- forms/
|   |-- mental_health/
|   |   |-- dass21/
|   |   |-- dass_y/
|   |   |-- gad7/
|   |   `-- phq9/
|   `-- physical_activity/
|       `-- ipaq/
|-- json/
|   |-- dass21.json
|   |-- dass_y.json
|   |-- gad7.json
|   |-- ipaq.json
|   `-- phq9.json
|-- references/
|   |-- json/  # Reviewed metadata records for licensed validation-study PDFs
|   `-- pdfs/  # Only studies explicitly cleared for redistribution
|-- inbox/     # Local PDF drop target; contents ignored by Git
|-- review/    # Local drafts and unapproved source PDFs; contents ignored
|-- build_catalog.py
|-- build_dass_catalog.py
`-- build_ipaq_catalog.py
```

Each PDF folder holds source forms for one instrument and domain. Each JSON represents one instrument family; each language, locale, population, and form is a separate `QuestionnaireVersion`. Its `source_documents` record holds the official URL, redistribution basis, retrieval date, local path, and SHA-256 digest.

Validation papers use a distinct `references/json/` metadata record and `references/pdfs/` asset path; they are never stored as questionnaire item JSON or mixed into an instrument form. Each reference record keeps title, instrument association, domain, language, authors, publication year, DOI/citations, PDF hash, license basis, and reviewer/date. The separate catalogue is populated only after human review confirms that bibliographic metadata and redistribution rights match the exact PDF.

For new uploads, use the Git-ignored [PDF inbox](inbox/README.md) and follow the [PDF intake guide](../../docs/pdf_intake.md). Unapproved files and drafts are never part of the shared catalogue.

## Bundled Forms

| Instrument | Included forms | Rights and evidence |
| --- | --- | --- |
| PHQ-9 | English; German for Germany | PHQ Screeners explicitly permits reproduction, translation, display, and distribution. Nine scored symptoms plus an unscored functional-impact item. |
| GAD-7 | English; German for Austria and Switzerland | Same official PHQ Screeners permission. Regional versions remain distinct. |
| DASS-21 | English; German (Nilges & Essau) | Official source says public domain and copyable, but not modifiable or for sale. Translation validity is not assured by the Foundation. |
| DASS-Y | English; German (Neuhoff & Noorani-Yazdanabad), ages 8-17 | Separate youth form. Scores are not interchangeable with adult DASS/DASS-21. Translation validity is not assured by the source. |
| IPAQ standard short self-administered | English; German translation, ages 15-69 | CC BY 4.0. Source-provided German form is supplied as-is; translation accuracy is not endorsed by the website. Numeric days and durations remain separate fields. |
| IPAQ-E | English, older-adult form | CC BY 4.0; kept separate from the standard short form. No numeric age range or MET score is invented. |

## Original Forms and Permissions

- **PHQ-9/GAD-7:** [official PHQ Screeners page](https://www.phqscreeners.com/select-screener) explicitly says no permission is required to reproduce, translate, display, or distribute its screeners and translations.
- **DASS/DASS-Y:** [official downloads](https://www2.psy.unsw.edu.au/dass/down.htm) say the forms are public domain/copyable, but may not be modified or sold. The [FAQ](https://www2.psy.unsw.edu.au/dass/DASSFAQ.htm) gives age guidance (adult DASS 14+; DASS-Y 8-17), says DASS-Y is not comparable to adult forms, and warns translations may not be validated by the Foundation.
- **IPAQ:** [official FAQ](https://sites.google.com/view/ipaq/faq) states CC BY 4.0; [official download page](https://sites.google.com/view/ipaq/download) says researcher-submitted translations are provided as-is and their accuracy is not checked.

Validation-study papers are linked by citation/DOI unless their own publication license separately permits bundling. A questionnaire-form permission is not blanket permission to copy its journal articles.

## Rebuild and Validate

The builders never download PDFs. They validate the local forms, recalculate checksums, and regenerate all five family JSON files:

```powershell
python data/questionnaires/build_catalog.py
python data/questionnaires/build_dass_catalog.py
python data/questionnaires/build_ipaq_catalog.py
pytest tests/unit/test_instrument_catalog.py -q
```

## Scoring, Populations, and Safety

- PHQ-9 contains nine scored symptom items; its functional-impact follow-up is explicitly unscored. Item 9 is tagged `suicide-related-thoughts` only for cautious interface presentation. That tag is not risk assessment or an escalation protocol.
- DASS-21 includes raw subscale sums and separate `x2` comparison outputs. DASS-Y remains unmultiplied and separate.
- IPAQ frequency and duration use numeric response fields and units; these test records do not calculate MET-minutes.
- DASS/IPAQ source-hosted translations are preserved verbatim but are not presumed independently validated or measurement-invariant.
- Screening scores alone do not establish a diagnosis. Real use requires the appropriate manuals, privacy/consent controls, trained interpretation, and locally reviewed response procedures.

## Adding Instruments

1. Identify the exact edition, language, locale, population, validation evidence, and official source.
2. Verify that item text and the actual PDF may be redistributed in a public repository. If rights are unclear, add only an official link and rights note to [the instrument library](../../docs/instrument_library.md).
3. Store every concrete form/translation as a separate version. Preserve source item wording, answer choices, numeric units, unscored follow-ups, scoring multipliers, and missing-data rules.
4. Bundle a PDF only with explicit permission. Record source URL, license, permission basis, access date, and checksum.
5. Add tests for item counts, exact source wording, scoring, age/locale variants, provenance, and search/filter behavior.

Never store participant responses, patient records, private publications, unauthorized forms, passwords, or API keys in this directory.
