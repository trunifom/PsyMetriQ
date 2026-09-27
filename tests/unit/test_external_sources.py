import asyncio
import json
from typing import Any
from urllib.request import Request

import pytest

from src.core import external_search_cli
from src.core.external_sources import (
    ExternalInstrumentCandidate,
    ExternalSourceError,
    NIHCDEClient,
    NLMClinicalTablesClient,
    PubMedClient,
)


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.body


def test_nlm_search_returns_preview_candidates_without_claiming_reuse_rights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        assert "terms=depression" in request.full_url
        assert timeout == 10
        return FakeResponse(
            [
                1,
                ["48542-5"],
                {"LONG_COMMON_NAME": ["Depression severity"]},
                [["Depression severity"]],
            ]
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    results = asyncio.run(NLMClinicalTablesClient().search_items("depression"))

    assert len(results) == 1
    assert results[0].source_id == "48542-5"
    assert results[0].preview_text == "Depression severity"
    assert results[0].rights_status == "not_assessed"
    assert "not a reuse license" in results[0].rights_note


def test_nlm_search_handles_empty_query_without_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_request(*_args: object, **_kwargs: object) -> FakeResponse:
        raise AssertionError("empty queries must not call the API")

    monkeypatch.setattr("urllib.request.urlopen", unexpected_request)

    assert asyncio.run(NLMClinicalTablesClient().search_items("  ")) == []


def test_nih_cde_search_previews_question_and_answer_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        assert request.method == "POST"
        assert timeout == 10
        body = json.loads(request.data or b"{}")
        assert body["searchTerm"] == "PHQ-9"
        return FakeResponse(
            {
                "docs": [
                    {
                        "tinyId": "example-id",
                        "designations": [
                            {"designation": "Question label", "tags": []},
                            {
                                "designation": "Little interest or pleasure",
                                "tags": ["Question Text"],
                            },
                        ],
                        "objectClass": {
                            "concepts": [{"name": "Patient Health Questionnaire"}]
                        },
                        "valueDomain": {
                            "permissibleValues": [
                                {
                                    "permissibleValue": "0",
                                    "valueMeaningName": "Not at all",
                                },
                                {
                                    "permissibleValue": "1",
                                    "valueMeaningName": "Several days",
                                },
                            ]
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    results = asyncio.run(NIHCDEClient().search_data_elements("PHQ-9"))

    assert len(results) == 1
    assert results[0].source == "nih_cde"
    assert results[0].preview_text == "Little interest or pleasure"
    assert results[0].instrument_name == "Patient Health Questionnaire"
    assert results[0].response_options == ["Not at all", "Several days"]
    assert results[0].rights_status == "not_assessed"


def test_pubmed_search_returns_citation_metadata_without_article_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        assert timeout == 10
        if "esearch.fcgi" in request.full_url:
            return FakeResponse({"esearchresult": {"idlist": ["12345"]}})
        return FakeResponse(
            {
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "title": "Validation study of a questionnaire",
                        "authors": [{"name": "Example Author"}],
                        "fulljournalname": "Journal of Measures",
                        "pubdate": "2025",
                        "articleids": [{"idtype": "doi", "value": "10.1234/example"}],
                    },
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    results = asyncio.run(PubMedClient().search("questionnaire validation"))

    assert len(results) == 1
    assert results[0].source_id == "12345"
    assert results[0].authors == ["Example Author"]
    assert results[0].doi == "10.1234/example"
    assert results[0].source_url.endswith("/12345/")
    assert not hasattr(results[0], "abstract")


def test_external_source_rejects_unexpected_nlm_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse({}))

    with pytest.raises(ExternalSourceError, match="unexpected response"):
        asyncio.run(NLMClinicalTablesClient().search_items("depression"))


def test_external_search_cli_displays_item_preview_and_rights_notice(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeNIHCDEClient:
        async def search_data_elements(
            self, _query: str, _limit: int
        ) -> list[ExternalInstrumentCandidate]:
            return [
                ExternalInstrumentCandidate(
                    source="nih_cde",
                    source_id="cde-1",
                    title="Example question",
                    preview_text="Example question",
                    instrument_name="Example instrument",
                    response_options=["Never", "Sometimes"],
                    source_url="https://cde.nlm.nih.gov/deView?tinyId=cde-1",
                    preview_kind="cde_data_element",
                )
            ]

    monkeypatch.setattr(external_search_cli, "NIHCDEClient", FakeNIHCDEClient)

    exit_code = external_search_cli.main(["Example", "--source", "nih-cde"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Example question" in output
    assert "Never; Sometimes" in output
    assert "Rights: not_assessed" in output