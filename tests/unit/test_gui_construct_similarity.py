"""GUI-level tests for the construct-similarity check; never loads a real model."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.core.nlp_engine import ConstructSimilarityMatch, NLPEngineError
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

    def show_dialog(self, dialog: Any) -> None:
        self.dialogs.append(dialog)

    def pop_dialog(self) -> Any:
        return self.dialogs.pop() if self.dialogs else None


def _app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PsyMetriQApplication:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", tmp_path / "admin_config.json")
    return PsyMetriQApplication(FakePage())  # type: ignore[arg-type]


def test_construct_similarity_check_reports_found_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    fake_matches = [
        ConstructSimilarityMatch(
            instrument_a="phq9",
            instrument_b="gad7",
            name_a="PHQ-9",
            name_b="GAD-7",
            similarity=0.81,
        )
    ]
    monkeypatch.setattr(application, "find_similar_constructs", lambda records: fake_matches)

    asyncio.run(app._check_construct_similarity(None))

    assert app.similarity_matches == fake_matches
    assert "1 Kandidatenpaar" in app.similarity_status
    panel = app._construct_similarity_panel()
    assert panel.subtitle is not None


def test_construct_similarity_check_reports_no_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    monkeypatch.setattr(application, "find_similar_constructs", lambda records: [])

    asyncio.run(app._check_construct_similarity(None))

    assert app.similarity_matches == []
    assert "Keine auffälligen" in app.similarity_status


def test_construct_similarity_check_surfaces_engine_errors_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)

    def fake_raise(records: Any) -> Any:
        raise NLPEngineError("sentence-transformers is not installed")

    monkeypatch.setattr(application, "find_similar_constructs", fake_raise)

    asyncio.run(app._check_construct_similarity(None))

    assert app.similarity_matches is None
    assert "Fehlgeschlagen" in app.similarity_status
