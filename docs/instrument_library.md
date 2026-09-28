# Instrument Library and Licensing Guide

## Purpose and date

This page is a curated discovery list for PsyMetriQ test records. It separates item-bearing instruments, selectable metadata-reference records, and candidates that still need source review. A restrictive or unverified license status is recorded and filterable; it does not remove an instrument from the research catalog or disable reference selection. Status reflects sources checked on **2026-09-28** and is not legal advice; verify exact terms before administering, adapting, distributing, or sharing item wording.

A scientific citation or public download page is not itself a redistribution licence. Rights can vary by instrument, edition, language, publisher, and intended use. A licence held by one university, research team, or end user does not automatically permit copying an item form into an open GitHub repository.

## Bundled, usable real test corpus

| Instrument | Topic | Forms included | Rights and evidence |
| --- | --- | --- | --- |
| PHQ-9 | Depressive symptoms / depression screening | English (`en-US`), German for Germany (`de-DE`) | The official PHQ Screeners page explicitly permits reproduction, translation, display, and distribution of PHQ screeners and translations. PDFs and source notices are in the data directory. |
| GAD-7 | Anxiety symptoms / generalized anxiety screening | English (`en-US`), German for Austria (`de-AT`), German for Switzerland (`de-CH`) | Same official reproduction statement; regional files are maintained separately to preserve their wording and response labels. |
| DASS-21 | Depression, anxiety, stress (adult forms) | English (`en-AU`), German (`de-DE`; Nilges & Essau translation) | Official Psychology Foundation says forms are public domain and may be copied, but not modified or sold. Translation accuracy/validity is not assured by the Foundation. |
| DASS-Y | Depression, anxiety, stress (youth) | English (`en-AU`), German (`de-DE`; Neuhoff & Noorani-Yazdanabad) | Official youth form is for ages 8-17, may be copied but not modified or sold. It is a separate instrument; scores are not comparable to adult DASS/DASS-21. |
| IPAQ Short Last 7 Days Self-Administered | Physical activity | English, German (`de-DE`); standard form states ages 15-69 | Official source licenses CC BY 4.0. Its site says researcher-submitted translations are provided as-is and their accuracy is not verified. Numeric day and duration fields are represented separately. |
| IPAQ-E | Physical activity (older-adult form) | English | CC BY 4.0 source form, kept as its own form. We do not infer an age cutoff or MET score that is not encoded with evidence. |
| Rosenberg Self-Esteem Scale | Self-esteem | English (`en-US`) | University of Maryland states the scale is public domain and permits use, translation, and adaptation with scholarly attribution. The bundled record flags the five reverse-coded items; score calculation is not performed by the GUI. |

The PDF source forms are organized in `data/questionnaires/forms/<domain>/<instrument>/`; each JSON family is in `data/questionnaires/json/`. The versions reference validation papers without bundling journal PDFs unless those publication rights are separately cleared.

## Selectable Reference Records

These records contain no local item wording, but can be searched, selected into projects, compared, and exported as metadata-only reference JSON. Each records source-reported length/dimensions where supported. Their presence does not grant permission to copy, adapt, administer, translate, or redistribute the source instrument.

| Instrument | Current record | Rights and current handling |
| --- | --- | --- |
| WHO-5 Well-Being Index | English; 5 items, positive wellbeing | Exact WHO-5 publication copyright notice and third-party credits have not been checked. The [WHO copyright policy](https://www.who.int/about/policies/publishing/copyright) requires checking the specific publication. |
| Warwick-Edinburgh Mental Wellbeing Scale (WEMWBS) | English; 14 items, mental wellbeing | Warwick's [non-commercial licence](https://warwick.ac.uk/services/innovations/wemwbs/licenses/non-commercial/) is free to eligible organisations after registration, valid for 12 months, and prohibits public sharing or onward provision under that licence. |
| Short Warwick-Edinburgh Mental Wellbeing Scale (SWEMWBS) | English short form; 7 items, mental wellbeing | Covered by Warwick's WEMWBS licence terms; no public rehosting. |
| General Self-Efficacy Scale (GSE) | English; 10 items, general self-efficacy | The [author-hosted source](https://userpage.fu-berlin.de/health/engscal.htm) describes form, response scale, population/scoring and language versions. No public redistribution grant was stated on reviewed pages. |
| Perceived Stress Scale (PSS-10/PSS-4) | English; 10/4 items, perceived stress | Carnegie Mellon's [official scale page](https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html) directs permission requests through MAPI/ePROVIDE. Requests are free, not approvals. |

## Broader catalogue for future versions

These instruments cover the domains requested for PsyMetriQ. They are discovery leads, not claims that the item text may be copied. Until the status says **bundled**, the repository contains no original item wording or source PDF for that instrument.

| Domain | Instrument candidates | Current handling |
| --- | --- | --- |
| Wellbeing | WHO-5 Well-Being Index; WEMWBS/SWEMWBS | WHO-5 and both Warwick forms are indexed as selectable metadata references. WHO-5's publication-specific rights need review; Warwick licence requires registration and disallows public sharing. |
| Stress | Perceived Stress Scale (PSS-10/PSS-4) | PSS-10 and PSS-4 have selectable English metadata references; Carnegie Mellon directs use-permission requests through MAPI/ePROVIDE. DASS is bundled but captures a narrower tension/stress construct. |
| Self-efficacy | General Self-Efficacy Scale (GSE) | English metadata reference with source-reported item count, response format, age guidance and score range; the author-hosted source's explicit redistribution terms remain unverified. |
| Anxiety | GAD-7; GAD-2; PROMIS Anxiety | GAD-7 and DASS anxiety are bundled. PROMIS has adult/pediatric forms and many languages; exact measure/translation terms apply. |
| Obsessive-compulsive symptoms | OCI-R (adult) | Common adult measure; MAPI/ePROVIDE is an authoritative discovery source. Item redistribution not established. |
| Depression | PHQ-9; DASS-21/DASS-Y; BDI-II; CES-D; GDS-15 | PHQ-9 and DASS variants are bundled under different terms. BDI-II is paid Pearson content; other editions need source-specific review. |
| Loneliness | UCLA Loneliness Scale v3 and short forms | Three-item version is widely used in surveys; German-language use is reported, but translation validation and redistribution rights need review. |
| Social support | MSPSS (12 items); ISEL-12 | MSPSS German psychometric work includes an older-adult sample. Exact form redistribution rights not established. |
| Social relationships/peers | KIDSCREEN-27/52; SDQ Peer Problems; Friendship Quality Questionnaire | KIDSCREEN covers ages 8-18 with German/English versions; exact rehosting rights need checking. SDQ is copyrighted; developer terms distinguish non-commercial copies. FQQ is a child measure; German validation/reuse not established. |
| Family relationships/structure | Family APGAR; ISQ/household roster measures | Family APGAR is a brief perceived family-function screen, not a family-structure measure. Capture household composition separately; confirm German evidence and form rights. |
| School attendance/absenteeism | ISAP/ISAP-P; SRAS-R | ISAP is a German-developed youth/parent attendance-problems inventory, initially validated in clinical child/adolescent samples; parent version shows limitations. SRAS-R is an English functional school-refusal measure; older German adaptation evidence questions equivalence. Redistribution not established. |
| School wellbeing | SSWQ; KIDSCREEN School Environment | SSWQ is a 16-item school measure initially validated in grades 6-8; German validation not established. KIDSCREEN is broader youth HRQoL. No forms bundled. |
| Media/internet/gaming | CIUS; IGDS9-SF; GADIS-A | CIUS has German adolescent and German/English adult validation studies. GADIS-A is a German ICD-11 gaming symptom screen validated for ages 10-17. IGDS9-SF is commonly used; exact translation evidence and item rights vary. |
| Socioeconomic status | Family Affluence Scale III; MacArthur Subjective Social Status ladder | FAS III is intended for school-age survey populations, not adult SES. MacArthur has separate adult and youth ladders. Check exact form/reproduction terms. |
| Resilience/resources | CD-RISC-10/25; Brief Resilience Scale | Widely used candidates, but exact scale rights and language/population validation must be checked; no forms bundled. |
| Physical/general health | PROMIS Global Health; WHODAS 2.0; EQ-5D-5L | PROMIS domains include adults (18+), pediatrics (8-17), and parent proxy (1-17); terms vary. WHODAS reproduction requires source-specific licensing. EuroQol registration/license terms apply. |
| Movement/physical activity | IPAQ short; IPAQ-E | Standard IPAQ short and English IPAQ-E are bundled. IPAQ German is official-site hosted but unvalidated by the site; use as a language fixture without asserting cross-locale measurement equivalence. |
| ADHD/attention | ASRS v1.1/ASRS-5 adult; ADHD-RS/Conners/Vanderbilt child forms | Reporter, age, and edition differ. Commercial/permission requirements apply to several child rating forms; no restricted items bundled. |
| Cognition/working memory/dementia | PROMIS Cognitive Function; NIH Toolbox; WAIS/WISC; MoCA; Mini-Cog | PROMIS/NIH have administration terms; WAIS/WISC are commercial; MoCA terms prohibit redistribution outside license. Mini-Cog public access is not an explicit GitHub redistribution grant. No forms bundled. |
| Substance use/addiction | AUDIT/ASSIST; CRAFFT 2.1; IGDS9-SF | WHO publications require exact-version/third-party review. CRAFFT is adolescent substance-risk screening and reproduction context approval is required. No forms bundled. |

## Validation and Population Evidence

The following references informed the shortlist. They identify original or key validation work, not blanket evidence for every translation, population, or cutoff:

- **MSPSS social support:** Zimet et al., 1988, [DOI 10.1207/s15327752jpa5201_2](https://doi.org/10.1207/s15327752jpa5201_2); German older-adult psychometric study, Boggatz, [DOI 10.1111/opn.12540](https://doi.org/10.1111/opn.12540).
- **UCLA loneliness short scale:** Hughes et al., 2004, [DOI 10.1177/0164027504268574](https://doi.org/10.1177/0164027504268574). German-language cohort use does not alone prove a validated translation.
- **KIDSCREEN:** Ravens-Sieberer et al., 2008, 22,827 children/adolescents ages 8-18 across 13 European countries, [DOI 10.1111/j.1524-4733.2007.00291.x](https://doi.org/10.1111/j.1524-4733.2007.00291.x).
- **Friendship Quality Questionnaire:** Parker & Asher, 1993, children in grades 3-5, [DOI 10.1037/0012-1649.29.4.611](https://doi.org/10.1037/0012-1649.29.4.611).
- **ISAP school attendance:** Knollmann, Reissner & Hebebrand, 2019, clinical youth sample, [DOI 10.1007/s00787-018-1204-2](https://doi.org/10.1007/s00787-018-1204-2); ISAP-P parent form, [DOI 10.3389/frcha.2025.1543527](https://doi.org/10.3389/frcha.2025.1543527). The parent validation found limitations in associations with absence; pair attendance-problem scales with actual attendance records.
- **School refusal:** Kearney's SRAS-R, 2002, [DOI 10.1023/A:1020774932043](https://doi.org/10.1023/A:1020774932043). A German adaptation study found concerns with the older adaptation's structure/content, so translation equivalence is not assumed.
- **School wellbeing:** Renshaw et al. SSWQ, 2015, grades 6-8, [DOI 10.1037/spq0000088](https://doi.org/10.1037/spq0000088).
- **Problematic internet use:** CIUS original, Meerkerk et al., 2009, [DOI 10.1089/cpb.2008.0181](https://doi.org/10.1089/cpb.2008.0181); German adolescent validation, [DOI 10.1089/cyber.2012.0689](https://doi.org/10.1089/cyber.2012.0689); German/English adult language invariance, [DOI 10.1089/cyber.2018.0731](https://doi.org/10.1089/cyber.2018.0731).
- **Gaming:** GADIS-A German ICD-11-based validation in frequent gamers ages 10-17, [DOI 10.3390/jcm9040993](https://doi.org/10.3390/jcm9040993); IGDS9-SF development, [DOI 10.1016/j.chb.2014.12.006](https://doi.org/10.1016/j.chb.2014.12.006). DSM-5 and ICD-11 measures are not interchangeable.
- **Family Affluence Scale III:** adolescent measure, Hartley et al., 2016, [DOI 10.1007/s12187-015-9325-3](https://doi.org/10.1007/s12187-015-9325-3); cross-national revision, [DOI 10.1007/s12187-015-9339-x](https://doi.org/10.1007/s12187-015-9339-x).
- **Subjective social status:** MacArthur ladder youth study, Goodman et al., 2001, [DOI 10.1542/peds.108.2.e31](https://doi.org/10.1542/peds.108.2.e31); adult foundational study, Adler et al., 2000, [DOI 10.1037/0278-6133.19.6.586](https://doi.org/10.1037/0278-6133.19.6.586).
- **IPAQ physical activity:** Craig et al. multicountry reliability/validity study, 2003, [DOI 10.1249/01.MSS.0000078924.61453.FB](https://doi.org/10.1249/01.MSS.0000078924.61453.FB). The source supports adult population surveillance; IPAQ-E remains a separate older-adult form.
- **WHO-5 wellbeing:** Topp et al. systematic review, 2015, [DOI 10.1159/000376585](https://doi.org/10.1159/000376585); exact instrument publication and third-party license still need checking before bundling.

No literature citation means a test is not validated; a citation does not establish item rights. For every adopted locale/form, preserve the exact study population and limitations in `QuestionnaireVersion` metadata.

## Authoritative discovery sources

- **PHQ/GAD-7:** [Official PHQ Screeners selection and download page](https://www.phqscreeners.com/select-screener) and its [terms](https://www.phqscreeners.com/terms). The source page states no permission is required to reproduce, translate, display, or distribute the listed screeners and translations.
- **DASS/DASS-Y:** [Official downloads](https://www2.psy.unsw.edu.au/dass/down.htm), [FAQ on age, scoring, use, and translations](https://www2.psy.unsw.edu.au/dass/DASSFAQ.htm), [adult translations](https://www2.psy.unsw.edu.au/dass/DASS%20Translations.htm), and [DASS-Y translations](https://www2.psy.unsw.edu.au/dass/DASS-Y%20Translations.htm). The source says public domain/copy allowed, not modified or sold; translations may not be validated by the Foundation.
- **IPAQ:** [Official download page](https://sites.google.com/view/ipaq/download) and [FAQ/license](https://sites.google.com/view/ipaq/faq). CC BY 4.0; translation submissions are provided as-is.
- **Rosenberg Self-Esteem Scale:** University of Maryland [public-domain and use notes](https://socy.umd.edu/quick-links/using-rosenberg-self-esteem-scale). The source notes original development on 5,024 New York high-school juniors/seniors; translation permission does not itself validate a translation.
- **General Self-Efficacy Scale:** [FU Berlin author's English page](https://userpage.fu-berlin.de/health/engscal.htm) gives the 10-item format, 4 response categories, 10-40 score range, and age guidance; the [language index](https://userpage.fu-berlin.de/health/selfscal.htm) lists available translations. No explicit public-rehosting grant was found on those reviewed pages.
- **WEMWBS/SWEMWBS:** [University of Warwick licence and pricing information](https://warwick.ac.uk/services/innovations/wemwbs/licenses/) and [non-commercial registration/terms](https://warwick.ac.uk/services/innovations/wemwbs/licenses/non-commercial/). The non-commercial licence is not permission to publicly share the scales.
- **WHO materials:** [WHO copyright and licensing policy](https://www.who.int/about/policies/publishing/copyright). Check the copyright notice on the specific publication and check for third-party material within it; a general WHO publication licence should not be assumed to apply to every embedded instrument.
- **Measurement-instrument selection:** [COSMIN](https://www.cosmin.nl/) offers guidance and discovery resources for measurement properties and instrument selection. A COSMIN listing or article does not grant item-text redistribution rights.
- **PROMIS:** [HealthMeasures](https://www.healthmeasures.net/explore-measurement-systems/promis) is the official starting point for measure access and applicable terms.
- **EQ-5D:** use the [EuroQol Group](https://euroqol.org/) as the authoritative source for instrument availability and licensing.
- **CD-RISC:** use the [CD-RISC official site](https://www.cd-risc.com/) to identify versions and permissions.
- **PSS:** [Cohen's Perceived Stress Scale resource page](https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html) is a discovery lead; verify current use/redistribution conditions for the exact version.
- **PSS permission workflow:** the same Carnegie Mellon page says use permission requests for the Perceived Stress Scale are submitted through [MAPI Research Trust ePROVIDE](https://eprovide.mapi-trust.org/). Apply for the exact form/language before building a bundled test record.
- **School attendance discovery:** [INSA attendance resources](https://insa.network/resources/research-based/) lists ISAP and related measures; check its linked primary research and separate reproduction rights.
- **Youth measures:** [KIDSCREEN versions](https://www.kidscreen.org/english/questionnaires/language-versions-view-and-download/) and [official SDQ forms](https://www.sdqinfo.org/py/sdqinfo/b0.py). Downloads do not necessarily grant permission to rehost PDFs; SDQ copyright/terms apply.
- **Problematic media use:** primary measure papers for [CIUS](https://doi.org/10.1089/cpb.2008.0181), [GADIS-A](https://doi.org/10.3390/jcm9040993), and [IGDS9-SF](https://doi.org/10.1016/j.chb.2014.12.006); check supplemental-form rights before copying.
- **Cognition/dementia:** [MoCA terms](https://mocacognition.com/terms-of-use/) prohibit redistribution outside the license; consult [HealthMeasures PROMIS](https://healthmeasures.net/promis-basics/) for exact cognitive forms and terms.

## Suggested evidence and metadata workflow

For each candidate version, capture the exact instrument title, edition/version ID, language tag, locale, short/full form, target population and age bounds only when source-supported, instrument-level and version-level contributors, citation/DOI, response period, scoring manual, and adaptation lineage. Store MeSH descriptors with verified IDs where possible. Record characteristics and searchable keywords separately from MeSH and ontology codes.

A source-document record should identify document type, source URL, local path only when a local copy is approved, licence name and URL, explicit redistribution status, permission basis, access date, and SHA-256 checksum. Keep research-article PDFs as links only unless their own rights permit redistribution.

If item text may not be redistributed, PsyMetriQ can still store permitted bibliographic and licensing metadata and provide an official link. Do not create a second-hand copy by transcribing, scanning, OCR, translating, or embedding restricted questions into JSON.

For technical details on extracting local PDFs, drafting JSON, human rights review, and promotion, see the [PDF intake guide](pdf_intake.md). The importer does not override the licensing rules in this catalogue.

## Scoring, ages, and evidence

Use primary validation studies and official manuals to distinguish the intended screening population from the population actually studied. Store evidence citations and age bounds on the specific version. Keep norms, thresholds, diagnostic sensitivity/specificity, and missing-data guidance traceable to the exact language/form/population; never transfer those values automatically to a translated or shortened form.

PsyMetriQ's bundled PHQ-9, GAD-7, DASS-21, DASS-Y, and IPAQ records are test data for software behavior. They do not substitute for official manuals, validation of a specific translation/population, or clinical interpretation. The IPAQ German translation is supplied by its source as-is; DASS translation quality is not assured by the Foundation.
