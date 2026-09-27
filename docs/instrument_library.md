# Instrument Library and Licensing Guide

## Purpose and date

This page is a curated discovery list for future PsyMetriQ test records. It separates instruments actually bundled in `data/questionnaires/` from instruments that still need source, population, translation, and redistribution review. Status reflects sources checked on **2026-09-27** and is not legal advice; verify the exact version's current terms before downloading, storing, processing, or sharing it.

A scientific citation or public download page is not itself a redistribution licence. Rights can vary by instrument, edition, language, publisher, and intended use. A licence held by one university, research team, or end user does not automatically permit copying an item form into an open GitHub repository.

## Bundled, usable real test corpus

| Instrument | Topic | Forms included | Rights and evidence |
| --- | --- | --- | --- |
| PHQ-9 | Depressive symptoms / depression screening | English (`en-US`), German for Germany (`de-DE`) | The official PHQ Screeners page explicitly permits reproduction, translation, display, and distribution of PHQ screeners and translations. PDFs and source notices are in the data directory. |
| GAD-7 | Anxiety symptoms / generalized anxiety screening | English (`en-US`), German for Austria (`de-AT`), German for Switzerland (`de-CH`) | Same official reproduction statement; regional files are maintained separately to preserve their wording and response labels. |

The versions reference their source validation papers by DOI without bundling those journal PDFs. The form redistribution permission is not treated as blanket permission to redistribute those publications.

## Broader catalogue for future versions

These instruments cover the domains requested for PsyMetriQ. They are discovery leads, not claims that the item text may be copied. Until the status says **bundled**, the repository contains no original item wording or source PDF for that instrument.

| Domain | Instrument candidates | Current handling |
| --- | --- | --- |
| Wellbeing | WHO-5 Well-Being Index; Warwick-Edinburgh Mental Wellbeing Scales (WEMWBS/SWEMWBS) | Link and evaluate exact version terms. Warwick's current non-commercial licence explicitly does not permit public sharing or providing the scale to other parties under that licence; do not bundle without separate redistribution permission. |
| Stress | Perceived Stress Scale (PSS-10/PSS-4) | Carnegie Mellon's official scale page directs users to request use permission through MAPI/ePROVIDE. No PSS items or PDFs are bundled until the project obtains and documents the applicable permission. |
| Anxiety | GAD-7; short form GAD-2; PROMIS Anxiety | GAD-7 is bundled. Add other versions only after rights and language/population evidence are reviewed. |
| Obsessive-compulsive symptoms | Obsessive-Compulsive Inventory-Revised (OCI-R) | Citation leads to the original paper; item-form redistribution status is not established here. Link only pending review. |
| Depression | PHQ-9; BDI-II; CES-D; Geriatric Depression Scale (GDS-15) | PHQ-9 is bundled. BDI-II is commercially distributed; GDS/CES-D terms and translations need source-specific review. |
| Loneliness | UCLA Loneliness Scale (version 3 and short forms) | Multiple versions and translations exist; exact source, population, validation, and distribution rights need review. |
| Social support | Multidimensional Scale of Perceived Social Support (MSPSS) | Literature/source identification is available; public redistribution of the selected form has not been verified. |
| Resilience/resources | Connor-Davidson Resilience Scale (CD-RISC-10/25); Brief Resilience Scale | Confirm exact scale rights and intended-use terms before storing real item text. |
| Physical/general health | PROMIS Global Health; EQ-5D-5L | PROMIS includes adult measures, pediatric measures for ages 8-17, and parent-proxy measures for ages 1-17 according to HealthMeasures. Exact measure use/redistribution terms still need review. EuroQol instruments require attention to official registration/licensing. No forms are bundled. |
| Younger populations | PHQ-A / adolescent depression forms; CES-DC; PROMIS Pediatric | Do not infer that adult PHQ-9/GAD-7 forms are validated for children. Locate age-specific editions, normative/validation evidence, translations, and redistribution terms first. |
| Older populations | GDS forms; age-specific PROMIS forms | Store the age range and supporting validation source on the exact version; do not label a form “elderly” based only on a search keyword. |

## Authoritative discovery sources

- **PHQ/GAD-7:** [Official PHQ Screeners selection and download page](https://www.phqscreeners.com/select-screener) and its [terms](https://www.phqscreeners.com/terms). The source page states no permission is required to reproduce, translate, display, or distribute the listed screeners and translations.
- **WEMWBS/SWEMWBS:** [University of Warwick licence and pricing information](https://warwick.ac.uk/services/innovations/wemwbs/licenses/) and [non-commercial registration/terms](https://warwick.ac.uk/services/innovations/wemwbs/licenses/non-commercial/). The non-commercial licence is not permission to publicly share the scales.
- **WHO materials:** [WHO copyright and licensing policy](https://www.who.int/about/policies/publishing/copyright). Check the copyright notice on the specific publication and check for third-party material within it; a general WHO publication licence should not be assumed to apply to every embedded instrument.
- **Measurement-instrument selection:** [COSMIN](https://www.cosmin.nl/) offers guidance and discovery resources for measurement properties and instrument selection. A COSMIN listing or article does not grant item-text redistribution rights.
- **PROMIS:** [HealthMeasures](https://www.healthmeasures.net/explore-measurement-systems/promis) is the official starting point for measure access and applicable terms.
- **EQ-5D:** use the [EuroQol Group](https://euroqol.org/) as the authoritative source for instrument availability and licensing.
- **CD-RISC:** use the [CD-RISC official site](https://www.cd-risc.com/) to identify versions and permissions.
- **PSS:** [Cohen's Perceived Stress Scale resource page](https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html) is a discovery lead; verify current use/redistribution conditions for the exact version.
- **PSS permission workflow:** the same Carnegie Mellon page says use permission requests for the Perceived Stress Scale are submitted through [MAPI Research Trust ePROVIDE](https://eprovide.mapi-trust.org/). Apply for the exact form/language before building a bundled test record.

## Suggested evidence and metadata workflow

For each candidate version, capture the exact instrument title, edition/version ID, language tag, locale, short/full form, target population and age bounds only when source-supported, instrument-level and version-level contributors, citation/DOI, response period, scoring manual, and adaptation lineage. Store MeSH descriptors with verified IDs where possible. Record characteristics and searchable keywords separately from MeSH and ontology codes.

A source-document record should identify document type, source URL, local path only when a local copy is approved, licence name and URL, explicit redistribution status, permission basis, access date, and SHA-256 checksum. Keep research-article PDFs as links only unless their own rights permit redistribution.

If item text may not be redistributed, PsyMetriQ can still store permitted bibliographic and licensing metadata and provide an official link. Do not create a second-hand copy by transcribing, scanning, OCR, translating, or embedding restricted questions into JSON.

## Scoring, ages, and evidence

Use primary validation studies and official manuals to distinguish the intended screening population from the population actually studied. Store evidence citations and age bounds on the specific version. Keep norms, thresholds, diagnostic sensitivity/specificity, and missing-data guidance traceable to the exact language/form/population; never transfer those values automatically to a translated or shortened form.

PsyMetriQ's bundled PHQ-9 and GAD-7 records are test data for software behavior. They are not a substitute for official manuals, independently evaluated German-region validation studies, or clinical interpretation.
