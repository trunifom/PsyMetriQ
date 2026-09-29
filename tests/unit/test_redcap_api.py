from typing import Any

import pytest

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireVersion,
    ResponseOption,
)
from src.exporters.redcap_api import (
    RedcapApiError,
    describe_project,
    pull_questionnaire_from_project,
    push_questionnaire_to_project,
)


class FakeRedcapProject:
    """In-memory stand-in for ``redcap.Project``; never touches the network."""

    def __init__(
        self,
        *,
        project_info: dict[str, Any] | None = None,
        metadata: list[dict[str, Any]] | None = None,
        raise_on: str | None = None,
    ) -> None:
        self._project_info = project_info or {
            "project_id": "42",
            "project_title": "Demo Study",
            "is_longitudinal": 0,
        }
        self._metadata = metadata if metadata is not None else []
        self._raise_on = raise_on
        self.imported: list[dict[str, Any]] | None = None

    def export_project_info(self, format_type: str = "json") -> dict[str, Any]:
        if self._raise_on == "export_project_info":
            raise RuntimeError("boom")
        return self._project_info

    def export_metadata(self, format_type: str = "json") -> list[dict[str, Any]]:
        if self._raise_on == "export_metadata":
            raise RuntimeError("boom")
        return self._metadata

    def import_metadata(self, to_import: list[dict[str, Any]], import_format: str = "json") -> Any:
        if self._raise_on == "import_metadata":
            raise RuntimeError("boom")
        self.imported = to_import
        return len(to_import)


def _demo_questionnaire() -> QuestionnaireParent:
    version = QuestionnaireVersion(
        version_id="v1",
        language="en",
        response_sets={
            "agree_2": [
                ResponseOption(code=0, label="No", score=0),
                ResponseOption(code=1, label="Yes", score=1),
            ]
        },
        items=[
            ItemSchema(
                item_id="q1",
                variable_name="q1",
                dimension="core",
                prompt_text="Demo item",
                response_set_ref="agree_2",
            )
        ],
    )
    return QuestionnaireParent(
        instrument_id="demo", name_full="Demo Instrument", is_commercial=False, versions=[version]
    )


def test_describe_project_reads_title_and_id() -> None:
    project = FakeRedcapProject()

    summary = describe_project(project)

    assert summary.project_id == "42"
    assert summary.project_title == "Demo Study"


def test_describe_project_wraps_failures() -> None:
    project = FakeRedcapProject(raise_on="export_project_info")

    with pytest.raises(RedcapApiError):
        describe_project(project)


def test_push_merges_new_fields_with_existing_metadata() -> None:
    project = FakeRedcapProject(
        metadata=[{"field_name": "record_id", "form_name": "demo"}]
    )
    questionnaire = _demo_questionnaire()

    result = push_questionnaire_to_project(project, questionnaire, questionnaire.versions[0])

    assert result.pushed_field_count == 1
    assert result.total_field_count == 2
    assert project.imported is not None
    field_names = {record["field_name"] for record in project.imported}
    assert field_names == {"record_id", "q1"}


def test_push_refuses_when_a_field_name_already_exists() -> None:
    project = FakeRedcapProject(metadata=[{"field_name": "q1", "form_name": "other_form"}])
    questionnaire = _demo_questionnaire()

    with pytest.raises(RedcapApiError, match="q1"):
        push_questionnaire_to_project(project, questionnaire, questionnaire.versions[0])

    assert project.imported is None


def test_push_wraps_import_failures_without_leaking_raw_exception() -> None:
    project = FakeRedcapProject(raise_on="import_metadata")
    questionnaire = _demo_questionnaire()

    with pytest.raises(RedcapApiError):
        push_questionnaire_to_project(project, questionnaire, questionnaire.versions[0])


def test_pull_reuses_the_csv_data_dictionary_parser() -> None:
    project = FakeRedcapProject(
        metadata=[
            {
                "field_name": "q1",
                "form_name": "demo",
                "section_header": "core",
                "field_type": "radio",
                "field_label": "Demo item",
                "select_choices_or_calculations": "0, No | 1, Yes",
                "required_field": "y",
            },
            {
                "field_name": "q_total",
                "form_name": "demo",
                "field_type": "calc",
                "field_label": "Total",
                "select_choices_or_calculations": "[q1]",
            },
        ]
    )

    imported = pull_questionnaire_from_project(project, language="en")

    assert len(imported.versions[0].items) == 1
    assert imported.versions[0].items[0].prompt_text == "Demo item"
    assert imported.versions[0].items[0].is_required is True
    assert "q_total (calc)" in (imported.metadata.notes or "")


def test_pull_refuses_an_empty_data_dictionary() -> None:
    project = FakeRedcapProject(metadata=[])

    with pytest.raises(RedcapApiError):
        pull_questionnaire_from_project(project)
