"""Tests for the one-time, per-instrument license acknowledgment gate.

The gate never grants redistribution rights (that remains the intake
pipeline's rights sidecar); it only decides whether the local GUI user has
confirmed, once per instrument per installation, that they will follow a
commercially restricted instrument's license terms before viewing/selecting
its item wording.
"""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    ResponseOption,
)
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


def _commercial_family() -> QuestionnaireParent:
    """A synthetic commercial instrument with real item text, for gate tests only."""
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "agree_5": [
                ResponseOption(code=0, label="Never", score=0),
                ResponseOption(code=1, label="Always", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="item_01",
                variable_name="item_01",
                dimension="core",
                prompt_text="A licensed synthetic test item.",
                response_set_ref="agree_5",
            )
        ],
        source_documents=[
            QuestionnaireSourceDocument(
                title="Licensed Test Manual",
                document_type="questionnaire_form",
                language="en",
                source_url="https://example.org/licensed-test",
                license_name="Commercial Publisher License",
                license_url="https://example.org/licensed-test/terms",
                redistribution_permitted=True,
                permission_basis="Institutional test library license for this study.",
                accessed_on=date(2026, 1, 1),
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id="licensed_demo",
        name_full="Licensed Demonstration Instrument",
        is_commercial=True,
        versions=[version],
    )


def _app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PsyMetriQApplication:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    app.catalog_records.append((_commercial_family(), Path("synthetic.json")))
    return app


def test_selecting_a_commercial_version_without_acknowledgment_shows_a_gate_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    family, version = app._find_version("licensed_demo", "v1")

    app._toggle_version(family, version, True)

    assert app._project_selection("licensed_demo", "v1") is None
    assert len(app.page.dialogs) == 1


def test_confirming_the_license_gate_persists_acknowledgment_and_completes_the_action(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    family, version = app._find_version("licensed_demo", "v1")

    app._toggle_version(family, version, True)
    dialog = app.page.dialogs[-1]
    confirm_button = dialog.actions[-1]
    import asyncio

    asyncio.run(confirm_button.on_click(None))

    assert app._project_selection("licensed_demo", "v1") is not None
    assert "licensed_demo" in app.settings.acknowledged_licenses
    saved = application.WorkspaceStore(tmp_path / "settings.json").load_settings()
    assert "licensed_demo" in saved.acknowledged_licenses


def test_already_acknowledged_instrument_selects_without_a_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    family, version = app._find_version("licensed_demo", "v1")
    app.settings = app.settings.model_copy(
        update={"acknowledged_licenses": {"licensed_demo": "2026-01-01T00:00:00+00:00"}}
    )

    app._toggle_version(family, version, True)

    assert app._project_selection("licensed_demo", "v1") is not None
    assert app.page.dialogs == []


def test_version_detail_hides_item_text_until_license_is_acknowledged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    app.active_version_key = ("licensed_demo", "v1")

    details = app._version_detail()
    rendered_text = _all_text_values(details)

    assert not any("licensed synthetic test item" in value for value in rendered_text)
    assert any("Lizenzpflichtig" in value or "Lizenz" in value for value in rendered_text)


def test_version_detail_reveals_item_text_after_acknowledgment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    app.settings = app.settings.model_copy(
        update={"acknowledged_licenses": {"licensed_demo": "2026-01-01T00:00:00+00:00"}}
    )
    app.active_version_key = ("licensed_demo", "v1")

    details = app._version_detail()
    rendered_text = _all_text_values(details)

    assert any("A licensed synthetic test item." in value for value in rendered_text)


def test_toggle_item_is_also_gated_directly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _app(monkeypatch, tmp_path)
    family, version = app._find_version("licensed_demo", "v1")

    app._toggle_item(family, version, "item_01", True)

    assert app._project_selection("licensed_demo", "v1") is None
    assert len(app.page.dialogs) == 1


def _all_text_values(control: Any) -> list[str]:
    """Recursively collect every ft.Text value under a control tree."""
    values: list[str] = []
    if isinstance(control, application.ft.Text) and isinstance(control.value, str):
        values.append(control.value)
    for attribute_name in ("content", "controls"):
        child = getattr(control, attribute_name, None)
        if child is None:
            continue
        if isinstance(child, list):
            for item in child:
                values.extend(_all_text_values(item))
        else:
            values.extend(_all_text_values(child))
    return values
