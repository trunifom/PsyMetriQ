"""Read-only connectors for public questionnaire discovery and evidence APIs.

External results are suggestions for human fit review, not trusted catalogue
records. In particular, an API response never establishes item reuse rights.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_RESULTS = 50


class ExternalSourceError(RuntimeError):
    """Raised when a public source is unavailable or returns an invalid response."""


class ExternalInstrumentCandidate(BaseModel):
    """A source-linked question/measurement candidate for preliminary fit review."""

    source: Literal["nih_cde", "nlm_clinical_tables"]
    source_id: str
    title: str
    source_url: str
    preview_text: str
    instrument_name: str | None = None
    response_options: list[str] = Field(default_factory=list)
    preview_kind: Literal["cde_data_element", "loinc_display_name"]
    rights_status: Literal["not_assessed"] = "not_assessed"
    rights_note: str = (
        "Public API visibility is not a reuse license. Confirm item and electronic-use "
        "permissions with the rights holder before adoption."
    )


class ExternalEvidenceRecord(BaseModel):
    """Bibliographic evidence metadata returned from PubMed."""

    source: Literal["pubmed"] = "pubmed"
    source_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    publication_date: str | None = None
    doi: str | None = None
    source_url: str

def _request_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    """Fetch bounded JSON from a fixed public API URL without logging query data."""
    request = urllib.request.Request(
        url,
        data=(
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else None
        ),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "PsyMetriQ/1.0 (academic questionnaire discovery)",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw_body = response.read(_MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as error:
        LOGGER.warning("External API request failed (%s)", type(error).__name__)
        raise ExternalSourceError("External source is temporarily unavailable") from None

    if len(raw_body) > _MAX_RESPONSE_BYTES:
        raise ExternalSourceError("External source response exceeded the size limit")
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ExternalSourceError("External source returned invalid JSON") from None


class NLMClinicalTablesClient:
    """Search public LOINC question/measurement display terms from the NLM."""

    endpoint = "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"

    async def search_items(self, query: str, limit: int = 10) -> list[ExternalInstrumentCandidate]:
        """Return LOINC display-name candidates; these are not full instrument records."""
        normalized_query = query.strip()
        if not normalized_query:
            return []
        result_limit = max(1, min(limit, _MAX_RESULTS))
        parameters = urllib.parse.urlencode(
            {
                "terms": normalized_query,
                "maxList": result_limit,
                "df": "LONG_COMMON_NAME",
                "ef": "LONG_COMMON_NAME,COMPONENT,SCALE_TYP,PROPERTY,SYSTEM,METHOD_TYP",
            }
        )
        response = await asyncio.to_thread(
            _request_json, f"{self.endpoint}?{parameters}"
        )
        if not isinstance(response, list) or len(response) < 4:
            raise ExternalSourceError("NLM Clinical Tables returned an unexpected response")

        codes = response[1]
        display_values = response[3]
        if not isinstance(codes, list) or not isinstance(display_values, list):
            raise ExternalSourceError("NLM Clinical Tables returned invalid result fields")

        candidates: list[ExternalInstrumentCandidate] = []
        for index, code in enumerate(codes[:result_limit]):
            display = display_values[index] if index < len(display_values) else None
            if not isinstance(code, str) or not code.strip():
                continue
            if isinstance(display, list):
                display = display[0] if display else None
            title = display.strip() if isinstance(display, str) else code
            candidates.append(
                ExternalInstrumentCandidate(
                    source="nlm_clinical_tables",
                    source_id=code,
                    title=title,
                    source_url=f"https://loinc.org/{urllib.parse.quote(code, safe='-')}/",
                    preview_text=title,
                    preview_kind="loinc_display_name",
                )
            )
        return candidates


class NIHCDEClient:
    """Search NIH Common Data Elements and preview source-reported item choices."""

    endpoint = "https://cde.nlm.nih.gov/api/de/search"

    async def search_data_elements(
        self, query: str, limit: int = 10
    ) -> list[ExternalInstrumentCandidate]:
        """Return CDE question candidates with answer labels when the source provides them."""
        normalized_query = query.strip()
        if not normalized_query:
            return []
        result_limit = max(1, min(limit, _MAX_RESULTS))
        response = await asyncio.to_thread(
            _request_json,
            self.endpoint,
            {"searchTerm": normalized_query, "page": 1, "resultPerPage": result_limit},
        )
        if not isinstance(response, dict) or not isinstance(response.get("docs"), list):
            raise ExternalSourceError("NIH CDE returned an unexpected search response")

        candidates: list[ExternalInstrumentCandidate] = []
        for document in response["docs"][:result_limit]:
            if not isinstance(document, dict):
                continue
            tiny_id = document.get("tinyId")
            designations = document.get("designations", [])
            if not isinstance(tiny_id, str) or not tiny_id.strip():
                continue
            if not isinstance(designations, list):
                designations = []
            question_text = self._question_text(designations)
            if not question_text:
                continue

            value_domain = document.get("valueDomain")
            permissible_values = (
                value_domain.get("permissibleValues", [])
                if isinstance(value_domain, dict)
                else []
            )
            response_options = (
                [
                    str(value.get("valueMeaningName") or value.get("permissibleValue"))
                    for value in permissible_values
                    if isinstance(value, dict)
                    and (value.get("valueMeaningName") or value.get("permissibleValue"))
                ]
                if isinstance(permissible_values, list)
                else []
            )
            candidates.append(
                ExternalInstrumentCandidate(
                    source="nih_cde",
                    source_id=tiny_id,
                    title=question_text,
                    preview_text=question_text,
                    instrument_name=self._instrument_name(document),
                    response_options=response_options,
                    source_url=(
                        "https://cde.nlm.nih.gov/deView?tinyId="
                        f"{urllib.parse.quote(tiny_id, safe='')}"
                    ),
                    preview_kind="cde_data_element",
                )
            )
        return candidates

    @staticmethod
    def _question_text(designations: list[Any]) -> str | None:
        """Prefer CDE designations explicitly tagged as question text."""
        valid_designations = [
            designation
            for designation in designations
            if isinstance(designation, dict)
            and isinstance(designation.get("designation"), str)
        ]
        for designation in valid_designations:
            tags = designation.get("tags", [])
            if isinstance(tags, list) and "Question Text" in tags:
                return designation["designation"].strip() or None
        for designation in valid_designations:
            if designation["designation"].strip():
                return designation["designation"].strip()
        return None

    @staticmethod
    def _instrument_name(document: dict[str, Any]) -> str | None:
        """Read an associated instrument label when the CDE record contains one."""
        for field_name in ("objectClass", "dataElementConcept"):
            concept_group = document.get(field_name)
            concepts = (
                concept_group.get("concepts", [])
                if isinstance(concept_group, dict)
                else []
            )
            if isinstance(concepts, list):
                for concept in concepts:
                    if isinstance(concept, dict) and isinstance(concept.get("name"), str):
                        return concept["name"]
        return None


class PubMedClient:
    """Search PubMed and return citation metadata without fetching article text."""

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    async def search(self, query: str, limit: int = 10) -> list[ExternalEvidenceRecord]:
        """Find bibliographic records suitable for linking as validation evidence."""
        normalized_query = query.strip()
        if not normalized_query:
            return []
        result_limit = max(1, min(limit, _MAX_RESULTS))
        search_parameters = urllib.parse.urlencode(
            {
                "db": "pubmed",
                "term": normalized_query,
                "retmode": "json",
                "retmax": result_limit,
            }
        )
        search_result = await asyncio.to_thread(
            _request_json,
            f"{self.base_url}/esearch.fcgi?{search_parameters}",
        )
        try:
            identifiers = search_result["esearchresult"]["idlist"]
        except (KeyError, TypeError):
            raise ExternalSourceError("PubMed returned an unexpected search response") from None
        if not isinstance(identifiers, list) or not identifiers:
            return []

        summary_parameters = urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(identifiers), "retmode": "json"}
        )
        summary_result = await asyncio.to_thread(
            _request_json,
            f"{self.base_url}/esummary.fcgi?{summary_parameters}",
        )
        try:
            records = summary_result["result"]
        except (KeyError, TypeError):
            raise ExternalSourceError("PubMed returned an unexpected summary response") from None
        if not isinstance(records, dict):
            raise ExternalSourceError("PubMed returned invalid citation records")

        evidence: list[ExternalEvidenceRecord] = []
        for identifier in identifiers:
            record = records.get(identifier)
            if not isinstance(record, dict):
                continue
            article_ids = record.get("articleids", [])
            doi = next(
                (
                    article_id.get("value")
                    for article_id in article_ids
                    if isinstance(article_id, dict)
                    and article_id.get("idtype") == "doi"
                    and isinstance(article_id.get("value"), str)
                ),
                None,
            )
            authors = record.get("authors", [])
            evidence.append(
                ExternalEvidenceRecord(
                    source_id=identifier,
                    title=str(record.get("title") or "Untitled PubMed record"),
                    authors=[
                        str(author["name"])
                        for author in authors
                        if isinstance(author, dict) and author.get("name")
                    ],
                    journal=record.get("fulljournalname") or None,
                    publication_date=record.get("pubdate") or None,
                    doi=doi,
                    source_url=f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/",
                )
            )
        return evidence