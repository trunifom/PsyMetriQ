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


class QuestionnaireVersion(BaseModel):
	"""Represent one language/version and its internally consistent item set."""

	version_id: str = Field(
		min_length=1, description="Version identifier unique within its instrument."
	)
	language: str = Field(
		min_length=2,
		max_length=5,
		description="Language tag for this version, for example 'de' or 'en-US'.",
	)
	cosmin_metrics: dict[str, Any] = Field(
		default_factory=dict,
		description="Psychometric quality metrics associated with this version.",
	)
	response_sets: dict[str, list[ResponseOption]] = Field(
		description="Named response scales referenced by this version's items."
	)
	items: list[ItemSchema] = Field(description="Items included in this questionnaire version.")
	scoring_algorithms: list[ScoringAlgorithm] = Field(
		default_factory=list,
		description="Optional score definitions that reference items in this version.",
	)

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
	versions: list[QuestionnaireVersion] = Field(
		min_length=1,
		description="Available language or release versions of this instrument.",
	)

	@model_validator(mode="after")
	def validate_version_ids(self) -> "QuestionnaireParent":
		"""Require version identifiers to be unique within this instrument."""
		version_ids = [version.version_id for version in self.versions]
		if len(version_ids) != len(set(version_ids)):
			raise ValueError("version_id values must be unique within a questionnaire")
		return self
