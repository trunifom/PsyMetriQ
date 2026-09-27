# External Source Search

PsyMetriQ currently provides read-only Python connectors for three public
services. They return temporary, source-linked candidates and do not write to
the local instrument catalogue.

## Implemented sources

| Connector | What it returns | What it does not establish |
|---|---|---|
| NIH CDE Repository | Data-element question text, related instrument label when available, and permissible response labels | That a result is a complete questionnaire, validated for a particular population, or reusable under a specific licence |
| NLM Clinical Tables / LOINC | Coded question or measurement display names and source links | Complete instrument items or psychometric validation; many matches are clinical measurements rather than questionnaire scales |
| PubMed | PMID, title, authors, journal, publication date, DOI, and PubMed link | Article full text or permission to copy questionnaire content from an article |

The NIH CDE connector prefers designations tagged `Question Text` and exposes
the source's answer labels when present. A CDE search may return score
definitions, individual questions, or related data elements; review the source
record and its relation to the full instrument before treating it as a form.

## Python usage

```python
import asyncio

from src.core.external_sources import NIHCDEClient, NLMClinicalTablesClient, PubMedClient


async def main() -> None:
    cde_candidates = await NIHCDEClient().search_data_elements("PHQ-9", limit=10)
    loinc_candidates = await NLMClinicalTablesClient().search_items("depression", limit=10)
    validation_studies = await PubMedClient().search(
        'PHQ-9[Title/Abstract] AND validation', limit=10
    )

    for candidate in cde_candidates:
        print(candidate.title, candidate.response_options, candidate.source_url)
    for study in validation_studies:
        print(study.title, study.doi, study.source_url)


asyncio.run(main())
```

These calls require internet access but no API key. Results are not cached or
persisted. Each call is limited to 50 results, uses a 10-second network timeout,
and rejects responses larger than 2 MB. PubMed returns citation metadata only;
the connector does not fetch abstracts or article text.

## Privacy and rights

Search terms are sent to the selected public provider. Do not include participant
identifiers, confidential study details, or other sensitive data in a query.
Connector errors are sanitized and do not log the query string.

Every instrument candidate has `rights_status="not_assessed"`. Public
availability, university affiliation, and non-commercial research intent do not
by themselves grant redistribution, electronic administration, adaptation,
translation, or platform-embedding rights. A university's existing subscription
or licence may grant additional access; confirm its scope with the library,
research office, and rights holder before reproducing or deploying items. Use
the previews to assess likely fit and identify the correct version, then request
the necessary permissions before adding the content to the PsyMetriQ catalogue
or an administered questionnaire.

The current Flet screen does not expose these connectors. Invoke them from
Python code, tests, or the CLI:

```powershell
python -m src.core.external_search_cli "PHQ-9" --source nih-cde
python -m src.core.external_search_cli "depression" --source loinc
python -m src.core.external_search_cli '"PHQ-9"[Title/Abstract] AND validation' --source pubmed
```

The CLI searches all three providers by default and prints source-linked results
and rights warnings. A user-facing federated search and source-by-source licence
review workflow remain future work. NIH CDE Forms, DataCite, PhenX file imports,
and licensed EBSCOhost/ePROVIDE integrations are not implemented yet.