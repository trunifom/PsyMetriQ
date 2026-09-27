import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from schemas.questionnaire_schema import (
    QuestionnaireContributor,
    QuestionnaireParent,
    QuestionnaireVersionReference,
    TargetPopulation,
)

LOGGER = logging.getLogger(__name__)


class QuestionnaireDataError(RuntimeError):
    """Raised when questionnaire files cannot be safely loaded."""


class QuestionnaireSearchResult(BaseModel):
    """A validated match that can be passed between application layers."""

    match_type: Literal["instrument", "version", "dimension", "item"]
    instrument_id: str
    instrument_name: str
    instrument_contributors: list[QuestionnaireContributor] = Field(default_factory=list)
    version_id: str | None = None
    version_name: str | None = None
    language: str | None = None
    locale: str | None = None
    form_type: str | None = None
    variant_types: list[str] = Field(default_factory=list)
    target_populations: list[TargetPopulation] = Field(default_factory=list)
    version_contributors: list[QuestionnaireContributor] = Field(default_factory=list)
    based_on: list[QuestionnaireVersionReference] = Field(default_factory=list)
    publication_year: int | None = None
    dimension: str | None = None
    item_id: str | None = None
    variable_name: str | None = None
    prompt_text: str | None = None
    matched_fields: list[str]


class QuestionnaireSearchEngine:
    """Search validated questionnaire JSON files without a database dependency.

    Source files remain ordinary portable JSON and may live in a local or
    synchronized team directory. Call :meth:`reload` after files are added or
    changed. A reload validates all files before replacing the current index,
    preserving the previous valid state when a file cannot be loaded.
    """

    def __init__(self, data_directory: Path | str) -> None:
        """Load all questionnaire JSON files from the provided directory."""
        self.data_directory = Path(data_directory)
        self._questionnaires: list[QuestionnaireParent] = []
        self.reload()

    def reload(self) -> int:
        """Validate and atomically replace the in-memory view of source files.

        Returns the number of valid instrument files. A missing or empty folder
        is a supported first-run state. Unreadable, invalid, or duplicate
        instruments are logged and raise :class:`QuestionnaireDataError`.
        """
        try:
            json_paths = sorted(self.data_directory.glob("*.json"))
        except OSError as error:
            LOGGER.exception("Could not list questionnaire files in %s", self.data_directory)
            raise QuestionnaireDataError("Could not list questionnaire files") from error

        loaded_questionnaires: list[QuestionnaireParent] = []
        instrument_ids: set[str] = set()
        for json_path in json_paths:
            try:
                questionnaire = QuestionnaireParent.model_validate_json(
                    json_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError) as error:
                LOGGER.error(
                    "Could not validate questionnaire file %s (%s)",
                    json_path.name,
                    type(error).__name__,
                )
                raise QuestionnaireDataError(
                    f"Invalid questionnaire data in {json_path.name}"
                ) from None

            if questionnaire.instrument_id in instrument_ids:
                LOGGER.error(
                    "Duplicate instrument_id %r found in questionnaire file %s",
                    questionnaire.instrument_id,
                    json_path.name,
                )
                raise QuestionnaireDataError(
                    f"Duplicate instrument_id {questionnaire.instrument_id!r}"
                )

            instrument_ids.add(questionnaire.instrument_id)
            loaded_questionnaires.append(questionnaire)

        self._questionnaires = loaded_questionnaires
        if loaded_questionnaires:
            LOGGER.info("Loaded %d questionnaire files", len(loaded_questionnaires))
        else:
            LOGGER.warning("No questionnaire JSON files found in %s", self.data_directory)
        return len(loaded_questionnaires)

    def search_items(self, keyword: str) -> list[QuestionnaireSearchResult]:
        """Search instrument and version metadata as well as item content.

        Matching is literal, case-insensitive substring search. Blank queries
        return no results. Results are validated models in deterministic source
        file, version, and item order. Structured population, contributor, and
        lineage metadata remains typed in the results for downstream consumers.
        """
        search_term = keyword.strip().casefold()
        if not search_term:
            return []

        results: list[QuestionnaireSearchResult] = []
        for questionnaire in self._questionnaires:
            instrument_contributors = questionnaire.contributors
            instrument_fields = {
                "instrument_id": questionnaire.instrument_id,
                "instrument_name": questionnaire.name_full,
                "construct_ontology": " ".join(questionnaire.construct_ontology),
                "instrument_contributors": " ".join(
                    f"{contributor.name} {contributor.role} {contributor.affiliation or ''}"
                    for contributor in instrument_contributors
                ),
            }
            instrument_matches = self._matching_fields(search_term, instrument_fields)
            if instrument_matches:
                results.append(
                    QuestionnaireSearchResult(
                        match_type="instrument",
                        instrument_id=questionnaire.instrument_id,
                        instrument_name=questionnaire.name_full,
                        instrument_contributors=instrument_contributors,
                        matched_fields=instrument_matches,
                    )
                )

            for version in questionnaire.versions:
                target_populations = version.target_populations
                version_contributors = version.contributors
                based_on = version.based_on
                population_search_text = " ".join(
                    " ".join(
                        str(value)
                        for value in (
                            population.group_name,
                            population.minimum_age_years,
                            population.maximum_age_years,
                            population.notes,
                        )
                        if value is not None
                    )
                    for population in target_populations
                )
                version_fields = {
                    "version_id": version.version_id,
                    "version_name": version.display_name or "",
                    "language": version.language,
                    "locale": version.locale or "",
                    "form_type": version.form_type,
                    "variant_types": " ".join(version.variant_types),
                    "target_populations": population_search_text,
                    "version_contributors": " ".join(
                        f"{contributor.name} {contributor.role} {contributor.affiliation or ''}"
                        for contributor in version_contributors
                    ),
                    "based_on": " ".join(
                        f"{reference.instrument_id} {reference.version_id}"
                        for reference in based_on
                    ),
                    "source_citation": version.source_citation or "",
                    "source_doi": version.source_doi or "",
                    "publication_year": str(version.publication_year or ""),
                }
                version_matches = self._matching_fields(search_term, version_fields)
                version_metadata = {
                    "version_id": version.version_id,
                    "version_name": version.display_name,
                    "language": version.language,
                    "locale": version.locale,
                    "form_type": version.form_type,
                    "variant_types": version.variant_types,
                    "target_populations": target_populations,
                    "version_contributors": version_contributors,
                    "based_on": based_on,
                    "publication_year": version.publication_year,
                }
                if version_matches:
                    results.append(
                        QuestionnaireSearchResult(
                            match_type="version",
                            instrument_id=questionnaire.instrument_id,
                            instrument_name=questionnaire.name_full,
                            instrument_contributors=instrument_contributors,
                            **version_metadata,
                            matched_fields=version_matches,
                        )
                    )

                matched_dimensions: set[str] = set()
                for item in version.items:
                    if (
                        search_term in item.dimension.casefold()
                        and item.dimension not in matched_dimensions
                    ):
                        results.append(
                            QuestionnaireSearchResult(
                                match_type="dimension",
                                instrument_id=questionnaire.instrument_id,
                                instrument_name=questionnaire.name_full,
                                instrument_contributors=instrument_contributors,
                                **version_metadata,
                                dimension=item.dimension,
                                matched_fields=["dimension"],
                            )
                        )
                        matched_dimensions.add(item.dimension)

                    response_labels = " ".join(
                        option.label for option in version.response_sets[item.response_set_ref]
                    )
                    item_fields = {
                        "item_id": item.item_id,
                        "variable_name": item.variable_name,
                        "dimension": item.dimension,
                        "prompt_text": item.prompt_text,
                        "response_options": response_labels,
                    }
                    item_matches = self._matching_fields(search_term, item_fields)
                    if item_matches:
                        results.append(
                            QuestionnaireSearchResult(
                                match_type="item",
                                instrument_id=questionnaire.instrument_id,
                                instrument_name=questionnaire.name_full,
                                instrument_contributors=instrument_contributors,
                                **version_metadata,
                                dimension=item.dimension,
                                item_id=item.item_id,
                                variable_name=item.variable_name,
                                prompt_text=item.prompt_text,
                                matched_fields=item_matches,
                            )
                        )

        return results

    @staticmethod
    def _matching_fields(search_term: str, fields: dict[str, str]) -> list[str]:
        """Return field names whose text contains the normalized query."""
        return [
            field_name
            for field_name, value in fields.items()
            if search_term in value.casefold()
        ]