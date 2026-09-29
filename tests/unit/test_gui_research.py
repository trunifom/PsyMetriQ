"""GUI-level tests for the instrument-recommendation research view."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.core.external_sources import ExternalInstrumentCandidate, ExternalSourceError
from src.core.nlp_engine import InstrumentMatch, NLPEngineError
from src.gui import application
from src.gui.application import PsyMetriQApplication


class FakePage:
    def __init__(self) -> None:
        self.services: list[Any] = []
        self.window = SimpleNamespace(min_width=None, min_height=None)
        self.controls: list[Any] = []
        self.update_count = 0
        self.dialogs: list[Any] = []

    def add(self, *controls: Any) -> None:
        self.controls.extend(controls)

    def update(self, *_controls: Any) -> None:
        self.update_count += 1


def _app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PsyMetriQApplication:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", tmp_path / "admin_config.json")
    return PsyMetriQApplication(FakePage())  # type: ignore[arg-type]


def test_catalog_search_reports_ranked_matches_and_renders_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    phq9 = app._find_family("phq9")
    assert phq9 is not None
    fake_matches = [InstrumentMatch(instrument_id="phq9", name_full="PHQ-9", similarity=0.87)]
    monkeypatch.setattr(
        application, "find_matching_instruments", lambda query, records: fake_matches
    )
    app.research_query = "depression"

    asyncio.run(app._search_catalog_instruments(None))

    assert app.research_matches == fake_matches
    assert "1 Treffer" in app.research_status
    controls = app._research_view()
    assert controls  # renders without raising


def test_catalog_search_reports_no_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    monkeypatch.setattr(application, "find_matching_instruments", lambda query, records: [])
    app.research_query = "an obscure construct"

    asyncio.run(app._search_catalog_instruments(None))

    assert app.research_matches == []
    assert "Keine Treffer" in app.research_status


def test_catalog_search_requires_a_query(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _app(monkeypatch, tmp_path)
    app.research_query = "   "

    asyncio.run(app._search_catalog_instruments(None))

    assert app.research_matches is None
    assert "Bitte zuerst" in app.research_status


def test_catalog_search_surfaces_engine_errors_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)

    def fake_raise(query: str, records: Any) -> Any:
        raise NLPEngineError("sentence-transformers is not installed")

    monkeypatch.setattr(application, "find_matching_instruments", fake_raise)
    app.research_query = "stress"

    asyncio.run(app._search_catalog_instruments(None))

    assert app.research_matches is None
    assert "Fehlgeschlagen" in app.research_status


def test_add_research_match_to_project_selects_the_first_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    phq9 = app._find_family("phq9")
    assert phq9 is not None

    app._add_research_match_to_project(phq9, phq9.versions[0])

    assert len(app._selected_versions()) == 1
    assert app._selected_versions()[0][0].instrument_id == "phq9"


def test_external_source_search_reports_candidates_and_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    fake_candidate = ExternalInstrumentCandidate(
        source="nih_cde",
        source_id="1234",
        title="Example CDE question",
        source_url="https://cde.nlm.nih.gov/deView?tinyId=1234",
        preview_text="Example CDE question",
        preview_kind="cde_data_element",
    )

    class FakeCDEClient:
        async def search_data_elements(self, query: str, limit: int = 8) -> Any:
            return [fake_candidate]

    class FakePubMedClient:
        async def search(self, query: str, limit: int = 5) -> Any:
            return []

    monkeypatch.setattr(application, "NIHCDEClient", FakeCDEClient)
    monkeypatch.setattr(application, "PubMedClient", FakePubMedClient)
    app.research_query = "stress"

    asyncio.run(app._search_external_sources(None))

    assert app.research_external_candidates == [fake_candidate]
    assert "1 NIH-CDE-Kandidat" in app.research_external_status
    controls = app._research_view()
    assert controls  # renders without raising


def test_external_source_search_surfaces_errors_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)

    class FailingClient:
        async def search_data_elements(self, query: str, limit: int = 8) -> Any:
            raise ExternalSourceError("External source is temporarily unavailable")

    monkeypatch.setattr(application, "NIHCDEClient", FailingClient)
    app.research_query = "stress"

    asyncio.run(app._search_external_sources(None))

    assert app.research_external_candidates is None
    assert "Fehlgeschlagen" in app.research_external_status
