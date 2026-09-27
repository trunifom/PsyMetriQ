import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from schemas.questionnaire_schema import (
    QuestionnaireContributor,
    QuestionnaireFormType,
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireVariantType,
    QuestionnaireVersion,
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
    is_commercial: bool
    construct_ontology: list[str] = Field(default_factory=list)
    instrument_contributors: list[QuestionnaireContributor] = Field(default_factory=list)
    instrument_metadata: QuestionnaireMetadata = Field(default_factory=QuestionnaireMetadata)
    version_id: str | None = None
    version_name: str | None = None
    language: str | None = None
    locale: str | None = None
    form_type: str | None = None
    variant_types: list[str] = Field(default_factory=list)
    target_populations: list[TargetPopulation] = Field(default_factory=list)
    version_contributors: list[QuestionnaireContributor] = Field(default_factory=list)
    based_on: list[QuestionnaireVersionReference] = Field(default_factory=list)
    version_metadata: QuestionnaireMetadata = Field(default_factory=QuestionnaireMetadata)
    publication_year: int | None = None
    dimension: str | None = None
    item_id: str | None = None
    variable_name: str | None = None
    prompt_text: str | None = None
    item_metadata: QuestionnaireMetadata = Field(default_factory=QuestionnaireMetadata)
    matched_fields: list[str]


class QuestionnaireSearchFilters(BaseModel):
    """Validated, composable filters for the searchable questionnaire catalogue.

    Multiple values inside one filter are alternatives (OR). Different filter
    categories are combined (AND). Metadata tags match exact normalized values;
    free-text notes and aliases remain available through the keyword query.
    """

    languages: list[str] = Field(default_factory=list)
    locales: list[str] = Field(default_factory=list)
    form_types: list[QuestionnaireFormType] = Field(default_factory=list)
    variant_types: list[QuestionnaireVariantType] = Field(default_factory=list)
    target_populations: list[str] = Field(default_factory=list)
    construct_ontology: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    mesh_terms: list[str] = Field(default_factory=list)
    characteristics: list[str] = Field(default_factory=list)
    is_commercial: bool | None = None


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

    def search_items(
        self,
        keyword: str = "",
        filters: QuestionnaireSearchFilters | None = None,
    ) -> list[QuestionnaireSearchResult]:
        """Search files using optional text and structured, combinable filters.

        Free text uses case-insensitive substring matching across model content.
        Filter values are exact case-insensitive matches; alternatives inside a
        filter category use OR, while separate categories use AND. A filters-only
        query returns the matching items. Blank text without active filters returns
        no results. Structured metadata remains typed in every search result.
        """
        search_term = keyword.strip().casefold()
        filters_active = self._filters_are_active(filters)
        if not search_term and not filters_active:
            return []

        results: list[QuestionnaireSearchResult] = []
        for questionnaire in self._questionnaires:
            if (
                filters is not None
                and filters.is_commercial is not None
                and questionnaire.is_commercial != filters.is_commercial
            ):
                continue
            if filters is not None and not self._selected_value_matches(
                filters.construct_ontology, questionnaire.construct_ontology
            ):
                continue

            instrument_contributors = questionnaire.contributors
            family_result_fields = {
                "is_commercial": questionnaire.is_commercial,
                "construct_ontology": questionnaire.construct_ontology,
                "instrument_contributors": instrument_contributors,
                "instrument_metadata": questionnaire.metadata,
            }
            instrument_fields = {
                "instrument_id": questionnaire.instrument_id,
                "instrument_name": questionnaire.name_full,
                "construct_ontology": " ".join(questionnaire.construct_ontology),
                "instrument_contributors": " ".join(
                    f"{contributor.name} {contributor.role} {contributor.affiliation or ''}"
                    for contributor in instrument_contributors
                ),
                "metadata": self._metadata_search_text(questionnaire.metadata),
            }
            instrument_matches = self._matching_fields(search_term, instrument_fields)
            instrument_result_added = False

            for version in questionnaire.versions:
                if not self._matches_version_filters(version, filters):
                    continue

                eligible_items = [
                    item
                    for item in version.items
                    if self._matches_metadata_filters(
                        filters, questionnaire.metadata, version.metadata, item.metadata
                    )
                ]
                if not eligible_items:
                    continue

                if search_term and instrument_matches and not instrument_result_added:
                    results.append(
                        QuestionnaireSearchResult(
                            match_type="instrument",
                            instrument_id=questionnaire.instrument_id,
                            instrument_name=questionnaire.name_full,
                            **family_result_fields,
                            matched_fields=instrument_matches,
                        )
                    )
                    instrument_result_added = True

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
                    "metadata": self._metadata_search_text(version.metadata),
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
                    "version_metadata": version.metadata,
                }

                if version_matches:
                    results.append(
                        QuestionnaireSearchResult(
                            match_type="version",
                            instrument_id=questionnaire.instrument_id,
                            instrument_name=questionnaire.name_full,
                            **family_result_fields,
                            **version_metadata,
                            matched_fields=version_matches,
                        )
                    )

                matched_dimensions: set[str] = set()
                for item in eligible_items:
                    item_metadata_text = self._metadata_search_text(item.metadata)
                    response_labels = " ".join(
                        option.label for option in version.response_sets[item.response_set_ref]
                    )
                    item_fields = {
                        "item_id": item.item_id,
                        "variable_name": item.variable_name,
                        "dimension": item.dimension,
                        "prompt_text": item.prompt_text,
                        "response_options": response_labels,
                        "metadata": item_metadata_text,
                    }
                    item_matches = (
                        self._matching_fields(search_term, item_fields) if search_term else []
                    )

                    if (
                        search_term
                        and search_term in item.dimension.casefold()
                        and item.dimension not in matched_dimensions
                    ):
                        results.append(
                            QuestionnaireSearchResult(
                                match_type="dimension",
                                instrument_id=questionnaire.instrument_id,
                                instrument_name=questionnaire.name_full,
                                **family_result_fields,
                                **version_metadata,
                                dimension=item.dimension,
                                matched_fields=["dimension"],
                            )
                        )
                        matched_dimensions.add(item.dimension)

                    if item_matches or filters_active:
                        results.append(
                            QuestionnaireSearchResult(
                                match_type="item",
                                instrument_id=questionnaire.instrument_id,
                                instrument_name=questionnaire.name_full,
                                **family_result_fields,
                                **version_metadata,
                                dimension=item.dimension,
                                item_id=item.item_id,
                                variable_name=item.variable_name,
                                prompt_text=item.prompt_text,
                                item_metadata=item.metadata,
                                matched_fields=item_matches or ["filters"],
                            )
                        )

        return results

    @staticmethod
    def _filters_are_active(filters: QuestionnaireSearchFilters | None) -> bool:
        """Return whether any filter contains a selected value."""
        if filters is None:
            return False
        return any(
            (
                filters.languages,
                filters.locales,
                filters.form_types,
                filters.variant_types,
                filters.target_populations,
                filters.construct_ontology,
                filters.keywords,
                filters.mesh_terms,
                filters.characteristics,
                filters.is_commercial is not None,
            )
        )

    @staticmethod
    def _selected_value_matches(selected: list[str], available: list[str]) -> bool:
        """Apply OR semantics to values in one exact-match filter category."""
        if not selected:
            return True
        normalized_available = {value.casefold() for value in available}
        return any(value.casefold() in normalized_available for value in selected)

    @classmethod
    def _matches_version_filters(
        cls,
        version: QuestionnaireVersion,
        filters: QuestionnaireSearchFilters | None,
    ) -> bool:
        """Check form-level fields while leaving content tags for item-level matching."""
        if filters is None:
            return True
        return (
            cls._selected_value_matches(filters.languages, [version.language])
            and cls._selected_value_matches(filters.locales, [version.locale or ""])
            and cls._selected_value_matches(filters.form_types, [version.form_type])
            and cls._selected_value_matches(filters.variant_types, version.variant_types)
            and cls._selected_value_matches(
                filters.target_populations,
                [population.group_name for population in version.target_populations],
            )
        )

    @classmethod
    def _matches_metadata_filters(
        cls,
        filters: QuestionnaireSearchFilters | None,
        *metadata_values: QuestionnaireMetadata,
    ) -> bool:
        """Match metadata filters across family, version, and item scopes."""
        if filters is None:
            return True
        available_keywords = [
            keyword for metadata in metadata_values for keyword in metadata.keywords
        ]
        available_mesh_values = [
            value
            for metadata in metadata_values
            for term in metadata.mesh_terms
            for value in (term.descriptor, term.descriptor_id or "")
        ]
        available_characteristics = [
            characteristic
            for metadata in metadata_values
            for characteristic in metadata.characteristics
        ]
        return (
            cls._selected_value_matches(filters.keywords, available_keywords)
            and cls._selected_value_matches(filters.mesh_terms, available_mesh_values)
            and cls._selected_value_matches(
                filters.characteristics, available_characteristics
            )
        )

    @staticmethod
    def _metadata_search_text(metadata: QuestionnaireMetadata) -> str:
        """Flatten searchable metadata for matching without changing its stored shape."""
        mesh_text = " ".join(
            " ".join([term.descriptor, term.descriptor_id or "", *term.qualifiers])
            for term in metadata.mesh_terms
        )
        return " ".join(
            [
                *metadata.keywords,
                *metadata.search_aliases,
                *metadata.characteristics,
                mesh_text,
                metadata.notes or "",
            ]
        )

    @staticmethod
    def _matching_fields(search_term: str, fields: dict[str, str]) -> list[str]:
        """Return field names whose text contains the normalized query."""
        return [
            field_name
            for field_name, value in fields.items()
            if search_term in value.casefold()
        ]