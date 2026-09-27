"""Command-line entry point for read-only public source discovery."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from src.core.external_sources import (
    ExternalEvidenceRecord,
    ExternalInstrumentCandidate,
    ExternalSourceError,
    NIHCDEClient,
    NLMClinicalTablesClient,
    PubMedClient,
)

_SOURCE_CHOICES = ("all", "nih-cde", "loinc", "pubmed")
_MAX_RESULTS = 50


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search public questionnaire and validation-evidence sources."
    )
    parser.add_argument("query", help="Search terms sent to the selected public providers")
    parser.add_argument(
        "--source",
        choices=_SOURCE_CHOICES,
        default="all",
        help="Source to query (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=f"Maximum results per source, from 1 to {_MAX_RESULTS} (default: 10)",
    )
    return parser


def _render_results(
    source_name: str,
    records: list[ExternalInstrumentCandidate] | list[ExternalEvidenceRecord],
) -> str:
    lines = [f"[{source_name}] {len(records)} result(s)"]
    for record in records:
        lines.append(f"- {record.title}")
        lines.append(f"  ID: {record.source_id}")
        if isinstance(record, ExternalInstrumentCandidate):
            if record.instrument_name:
                lines.append(f"  Instrument: {record.instrument_name}")
            if record.response_options:
                lines.append(f"  Response options: {'; '.join(record.response_options)}")
            lines.append(f"  Rights: {record.rights_status}; verify before adoption")
        else:
            citation_parts = [
                value
                for value in (
                    ", ".join(record.authors),
                    record.journal,
                    record.publication_date,
                    f"DOI {record.doi}" if record.doi else None,
                )
                if value
            ]
            if citation_parts:
                lines.append(f"  Citation: {'; '.join(citation_parts)}")
        lines.append(f"  Source: {record.source_url}")
    return "\n".join(lines)


async def _search_source(
    source: str, query: str, limit: int
) -> tuple[
    str,
    list[ExternalInstrumentCandidate] | list[ExternalEvidenceRecord] | None,
    str | None,
]:
    try:
        if source == "nih-cde":
            results = await NIHCDEClient().search_data_elements(query, limit)
        elif source == "loinc":
            results = await NLMClinicalTablesClient().search_items(query, limit)
        else:
            results = await PubMedClient().search(query, limit)
        return source, results, None
    except ExternalSourceError as error:
        return source, None, str(error)


async def async_main(arguments: Sequence[str] | None = None) -> int:
    """Search selected providers and print source-linked, non-persisted results."""
    parser = _parser()
    parsed = parser.parse_args(arguments)
    if not 1 <= parsed.limit <= _MAX_RESULTS:
        parser.error(f"--limit must be between 1 and {_MAX_RESULTS}")
    sources = (
        ("nih-cde", "loinc", "pubmed")
        if parsed.source == "all"
        else (parsed.source,)
    )
    outcomes = await asyncio.gather(
        *(_search_source(source, parsed.query, parsed.limit) for source in sources)
    )

    has_results = False
    for source, results, error in outcomes:
        if error:
            print(f"[{source}] Search unavailable: {error}", file=sys.stderr)
            continue
        if results:
            has_results = True
        print(_render_results(source, results or []))
    if not has_results and all(error is None for _, _, error in outcomes):
        print("No candidates found.")
    return int(not has_results and any(error for _, _, error in outcomes))


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the async source search from a standard Python console entry point."""
    return asyncio.run(async_main(arguments))


if __name__ == "__main__":
    raise SystemExit(main())