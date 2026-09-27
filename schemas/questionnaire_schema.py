import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ResponseOption(BaseModel):
	"""A coded response and its numeric value for scoring an item."""

	code: str | int = Field(description="Stable response code stored with collected answers.")
	label: str = Field(min_length=1, description="Human-readable response shown to a respondent.")
	score: float = Field(description="Numeric value used by scoring algorithms.")


class ItemSchema(BaseModel):
	"""A single questionnaire item using a REDCap-compatible field name."""

	item_id: str = Field(min_length=1, description="Stable identifier unique within a version.")
	variable_name: str = Field(
		min_length=1,
		max_length=26,
		description=(
			"REDCap field name: starts with a letter; letters, digits, and underscores only."
		),
	)
	dimension: str = Field(
		min_length=1, description="Subscale or construct dimension for this item."
	)
	prompt_text: str = Field(min_length=1, description="Text presented to the respondent.")
	response_set_ref: str = Field(
		min_length=1,
		description="Key of the response set defined by the containing questionnaire version.",
	)
	is_reverse_scored: bool = Field(
		default=False,
		description="Whether this item's score direction must be reversed during scoring.",
	)
	redcap_field_type: Literal["radio", "checkbox", "slider", "text"] = Field(
		default="radio", description="REDCap field type used when exporting this item."
	)

	@field_validator("variable_name")
	@classmethod
	def validate_variable_name(cls, value: str) -> str:
		"""Enforce the 26-character alphanumeric-and-underscore naming convention."""
		if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,25}", value) is None:
			raise ValueError(
				"variable_name must start with a letter and contain only letters, "
				"numbers, or underscores (maximum 26 characters)"
			)
		return value


class ScoringAlgorithm(BaseModel):
	"""Describe how a set of item identifiers contributes to a derived score."""

	output_variable: str = Field(min_length=1, description="Name assigned to the derived score.")
	method: Literal["sum", "mean", "weighted"] = Field(
		description="Scoring operation applied to the referenced items."
	)
	target_items: list[str] = Field(
		min_length=1,
		description="Item identifiers from the containing version used to calculate the score.",
	)
	missing_data_rules: str | None = Field(
		default=None,
		description="Human-readable rule describing how missing item answers are handled.",
	)


class QuestionnaireContributor(BaseModel):
	"""Credit a person or group for a specific role in instrument development."""

	name: str = Field(min_length=1, description="Person or group name as cited by the source.")
	role: Literal["author", "translator", "adapter", "editor", "reviewer", "validator", "other"]
	affiliation: str | None = Field(
		default=None, description="Affiliation reported by the source, if available."
	)
	orcid: str | None = Field(
		default=None, description="ORCID identifier, if verified and available."
	)


class TargetPopulation(BaseModel):
	"""Describe an intended respondent group without assuming clinical eligibility."""

	group_name: str = Field(
		min_length=1, description="Population label, such as adolescents or adults."
	)
	minimum_age_years: float | None = Field(default=None, ge=0)
	maximum_age_years: float | None = Field(default=None, ge=0)
	notes: str | None = Field(
		default=None,
		description="Source-reported population details that do not fit structured age fields.",
	)

	@model_validator(mode="after")
	def validate_age_range(self) -> "TargetPopulation":
		"""Reject an age range whose minimum is greater than its maximum."""
		if (
			self.minimum_age_years is not None
			and self.maximum_age_years is not None
			and self.minimum_age_years > self.maximum_age_years
		):
			raise ValueError("minimum_age_years cannot exceed maximum_age_years")
		return self


class QuestionnaireVersionReference(BaseModel):
	"""Identify a source version that a translation or adaptation was based on."""

	instrument_id: str = Field(min_length=1)
	version_id: str = Field(min_length=1)


class QuestionnaireVersion(BaseModel):
	"""Represent one concrete form, language, audience, and item set."""

	version_id: str = Field(
		min_length=1, description="Version identifier unique within its instrument."
	)
	language: str = Field(
		min_length=2,
		max_length=35,
		description="BCP 47 language tag, for example 'de', 'en-US', or 'zh-Hans-CN'.",
	)
	display_name: str | None = Field(
		default=None,
		description="Human-readable edition name, such as 'Adolescent Short Form'.",
	)
	locale: str | None = Field(
		default=None,
		description="Regional locale or adaptation context, such as 'de-DE' or 'de-CH'.",
	)
	form_type: Literal["full", "short", "long", "screening", "custom"] = Field(
		default="full",
		description="Questionnaire form length or intended administration form.",
	)
	variant_types: list[
		Literal[
			"revision",
			"translation",
			"cultural_adaptation",
			"population_adaptation",
			"extension",
			"validation",
		]
	] = Field(
		default_factory=list,
		description="All applicable ways this form differs from or extends another version.",
	)
	target_populations: list[TargetPopulation] = Field(
		default_factory=list,
		description="Source-reported respondent groups for this form.",
	)
	contributors: list[QuestionnaireContributor] = Field(
		default_factory=list,
		description="Authors, translators, adaptors, and other version-specific contributors.",
	)
	based_on: list[QuestionnaireVersionReference] = Field(
		default_factory=list,
		description="Source versions this version was derived from.",
	)
	publication_year: int | None = Field(
		default=None, ge=1000, le=2200, description="Publication year of this version, if known."
	)
	source_citation: str | None = Field(
		default=None, description="Bibliographic citation for this version, if known."
	)
	source_doi: str | None = Field(
		default=None, description="DOI for the primary version source, if available."
	)
	cosmin_metrics: dict[str, Any] = Field(
		default_factory=dict,
		description="Psychometric quality metrics associated with this version.",
	)
	response_sets: dict[str, list[ResponseOption]] = Field(
		min_length=1,
		description="Named response scales referenced by this version's items."
	)
	items: list[ItemSchema] = Field(
		min_length=1,
		description="Items included in this questionnaire version.",
	)
	scoring_algorithms: list[ScoringAlgorithm] = Field(
		default_factory=list,
		description="Optional score definitions that reference items in this version.",
	)

	@field_validator("language", "locale")
	@classmethod
	def validate_language_tag(cls, value: str | None) -> str | None:
		"""Validate a practical BCP 47 tag shape while preserving source spelling."""
		if value is None:
			return None
		if re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", value) is None:
			raise ValueError("language and locale must use a valid BCP 47 tag shape")
		return value

	@model_validator(mode="after")
	def validate_references(self) -> "QuestionnaireVersion":
		"""Reject duplicate identifiers and references that cannot resolve locally."""
		item_ids = [item.item_id for item in self.items]
		if len(item_ids) != len(set(item_ids)):
			raise ValueError("item_id values must be unique within a questionnaire version")

		# REDCap field names are treated case-insensitively to prevent collisions.
		variable_names = [item.variable_name.casefold() for item in self.items]
		if len(variable_names) != len(set(variable_names)):
			raise ValueError("variable_name values must be unique within a questionnaire version")

		for item in self.items:
			if item.response_set_ref not in self.response_sets:
				raise ValueError(
					f"Item {item.item_id!r} references unknown response set "
					f"{item.response_set_ref!r}"
				)

		for algorithm in self.scoring_algorithms:
			unknown_items = set(algorithm.target_items) - set(item_ids)
			if unknown_items:
				raise ValueError(
					f"Scoring algorithm {algorithm.output_variable!r} references "
					f"unknown items: {sorted(unknown_items)}"
				)

		return self


class QuestionnaireParent(BaseModel):
	"""Group questionnaire versions under one stable instrument identifier."""

	instrument_id: str = Field(min_length=1, description="Stable identifier for the instrument.")
	name_full: str = Field(min_length=1, description="Full human-readable instrument name.")
	construct_ontology: list[str] = Field(
		default_factory=list,
		description="Ontology identifiers associated with the measured construct.",
	)
	is_commercial: bool = Field(
		description="Whether use of this instrument is commercially restricted."
	)
	contributors: list[QuestionnaireContributor] = Field(
		default_factory=list,
		description="Original instrument-level authors or groups, when known.",
	)
	versions: list[QuestionnaireVersion] = Field(
		min_length=1,
		description="Available language or release versions of this instrument.",
	)

	@model_validator(mode="after")
	def validate_version_ids(self) -> "QuestionnaireParent":
		"""Validate version IDs and local lineage references for this instrument."""
		version_ids = [version.version_id for version in self.versions]
		if len(version_ids) != len(set(version_ids)):
			raise ValueError("version_id values must be unique within a questionnaire")

		local_parents: dict[str, list[str]] = {version_id: [] for version_id in version_ids}
		for version in self.versions:
			for reference in version.based_on:
				if reference.instrument_id != self.instrument_id:
					continue
				if reference.version_id not in local_parents:
					raise ValueError(
						f"Version {version.version_id!r} references unknown local version "
						f"{reference.version_id!r}"
					)
				if reference.version_id == version.version_id:
					raise ValueError("A questionnaire version cannot be based on itself")
				local_parents[version.version_id].append(reference.version_id)

		visited: set[str] = set()
		visiting: set[str] = set()

		def visit(version_id: str) -> None:
			if version_id in visiting:
				raise ValueError("Questionnaire version lineage cannot contain cycles")
			if version_id in visited:
				return
			visiting.add(version_id)
			for parent_version_id in local_parents[version_id]:
				visit(parent_version_id)
			visiting.remove(version_id)
			visited.add(version_id)

		for version_id in version_ids:
			visit(version_id)
		return self
