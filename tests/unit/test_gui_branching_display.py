"""GUI display of item show_if/matrix metadata (informational only, no editor)."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from schemas.questionnaire_schema import (
    BranchingCondition,
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


def _family() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "yesno": [
                ResponseOption(code=1, label="Yes", score=None),
                ResponseOption(code=0, label="No", score=None),
            ]
        },
        items=[
            ItemSchema(
                item_id="gate_01",
                variable_name="gate_01",
                dimension="core",
                prompt_text="Have you ever smoked?",
                response_set_ref="yesno",
            ),
            ItemSchema(
                item_id="follow_01",
                variable_name="follow_01",
                dimension="core",
                prompt_text="How many cigarettes per day?",
                response_mode="numeric",
                is_scored=False,
                show_if=[BranchingCondition(source_item_id="gate_01", value="1")],
                matrix_group_name="smoking_matrix",
                matrix_ranking=True,
            ),
        ],
        source_documents=[
            QuestionnaireSourceDocument(
                title="Demo Form",
                document_type="questionnaire_form",
                language="en",
                source_url="https://example.org/demo",
                license_name="Public domain",
                redistribution_permitted=True,
                permission_basis="Synthetic test fixture.",
                accessed_on=date(2026, 1, 1),
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id="branching_demo",
        name_full="Branching Logic Demonstration Instrument",
        is_commercial=False,
        versions=[version],
    )


def _all_text_values(control: Any) -> list[str]:
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


def test_version_detail_shows_show_if_and_matrix_group_info(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(application, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(application, "ADMIN_CONFIG_PATH", tmp_path / "admin_config.json")
    app = PsyMetriQApplication(FakePage())  # type: ignore[arg-type]
    app.catalog_records.append((_family(), Path("synthetic.json")))
    app.active_version_key = ("branching_demo", "v1")

    details = app._version_detail()
    rendered_text = _all_text_values(details)

    assert any("Nur sichtbar, wenn gate_01 = 1" in value for value in rendered_text)
    assert any("Matrixgruppe: smoking_matrix (Ranking)" in value for value in rendered_text)
