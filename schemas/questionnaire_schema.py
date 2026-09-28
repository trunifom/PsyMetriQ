import re
from datetime import date
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

QuestionnaireFormType: TypeAlias = Literal["full", "short", "long", "screening", "custom"]
QuestionnaireVariantType: TypeAlias = Literal[
	"revision",
	"translation",
	"cultural_adaptation",
	"population_adaptation",
	"extension",
	"validation",
]


class ResponseOption(BaseModel):
	"""A coded response and its numeric value for scoring an item."""

	code: str | int = Field(description="Stable response code stored with collected answers.")
	label: str = Field(min_length=1, description="Human-readable response shown to a respondent.")
	score: float | None = Field(
		description="Numeric scoring value, or None when the choice is not scored."
	)


class MeSHTerm(BaseModel):
	"""Represent a Medical Subject Headings term and its stable descriptor ID."""

	descriptor: str = Field(min_length=1, description="Human-readable MeSH descriptor.")
	descriptor_id: str | None = Field(
		default=None, description="MeSH Unique ID, when known and verified."
	)
	qualifiers: list[str] = Field(
		default_factory=list,
		description="Optional MeSH qualifiers that narrow the descriptor's meaning.",
	)


class QuestionnaireMetadata(BaseModel):
	"""Store search, filter, and human-review metadata at a domain level."""

	description: str | None = Field(
		default=None,
		description="Short source-grounded explanation of what the instrument is about.",
	)
	intended_use: str | None = Field(
		default=None,
		description="Documented purpose, setting, or use case; not a clinical authorization.",
	)
	name_origin: str | None = Field(
		default=None,
		description="Source-grounded explanation of the instrument name or abbreviation.",
	)
	development_history: str | None = Field(
		default=None,
		description="Brief documented development or revision history.",
	)
	measurement_rationale: str | None = Field(
		default=None,
		description="Documented theoretical or measurement rationale for the target construct.",
	)
	interpretation_notes: str | None = Field(
		default=None,
		description="Source-grounded interpretation, limitations, or population-specific cautions.",
	)

	keywords: list[str] = Field(
		default_factory=list,
		description="Curated keywords used for search and exact-match filters.",
	)
	search_aliases: list[str] = Field(
		default_factory=list,
		description="Synonyms, alternate names, or spelling variants for full-text search.",
	)
	mesh_terms: list[MeSHTerm] = Field(
		default_factory=list,
		description="MeSH descriptors and identifiers for controlled-vocabulary filtering.",
	)
	characteristics: list[str] = Field(
		default_factory=list,
		description="Searchable characteristics such as self-report or interviewer-administered.",
	)
	notes: str | None = Field(
		default=None,
		description="Editorial notes for review; never place secrets or participant data here.",
	)


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
	response_mode: Literal["categorical", "numeric", "text"] = Field(
		default="categorical",
		description="Whether the response is selected from a scale or entered numerically/as text.",
	)
	response_set_ref: str | None = Field(
		default=None,
		description="Key of a version response set; required for categorical responses.",
	)
	measurement_unit: str | None = Field(
		default=None,
		description="Unit for numeric input, such as days/week, minutes/day, or hours/day.",
	)
	numeric_minimum: float | None = Field(default=None)
	numeric_maximum: float | None = Field(default=None)
	is_reverse_scored: bool = Field(
		default=False,
		description="Whether this item's score direction must be reversed during scoring.",
	)
	is_required: bool = Field(
		default=False,
		description="Whether this item must be answered during administration.",
	)
	is_scored: bool = Field(
		default=True,
		description=(
			"Whether this item contributes to a derived score; auxiliary questions are false."
		),
	)
	redcap_field_type: Literal["radio", "checkbox", "slider", "text"] = Field(
		default="radio", description="REDCap field type used when exporting this item."
	)
	metadata: QuestionnaireMetadata = Field(
		default_factory=QuestionnaireMetadata,
		description="Item-specific tags or notes for discovery and review.",
	)

	@model_validator(mode="after")
	def validate_response_definition(self) -> "ItemSchema":
		"""Require scale references for categorical items and consistent numeric bounds."""
		if self.response_mode == "categorical" and self.response_set_ref is None:
			raise ValueError("Categorical items must reference a response set")
		if (
			self.numeric_minimum is not None
			and self.numeric_maximum is not None
			and self.numeric_minimum > self.numeric_maximum
		):
			raise ValueError("numeric_minimum cannot exceed numeric_maximum")
		return self

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
	multiplier: float = Field(
		default=1.0,
		description="Factor applied after the configured method, such as 2 for DASS-21 scales.",
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


class QuestionnaireSourceDocument(BaseModel):
	"""Record an authoritative source document and its local redistribution audit.

	The permission statement is specific to the source and this exact document;
	``redistribution_permitted`` must not be inferred from public accessibility.
	A local path is repository-relative and cannot escape the project directory.
	"""

	title: str = Field(min_length=1)
	document_type: Literal[
		"questionnaire_form", "validation_study", "user_manual", "bibliography", "other"
	]
	language: str = Field(min_length=2, max_length=35)
	source_url: HttpUrl | None = None
	local_path: str | None = None
	license_name: str = Field(min_length=1)
	license_url: HttpUrl | None = None
	redistribution_permitted: bool
	permission_basis: str = Field(min_length=1)
	accessed_on: date
	sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

	@field_validator("local_path")
	@classmethod
	def validate_local_path(cls, value: str | None) -> str | None:
		"""Reject absolute paths and traversal components in repository file links."""
		if value is None:
			return None
		path_parts = value.replace("\\", "/").split("/")
		if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
			raise ValueError("local_path must be repository-relative")
		if ".." in path_parts:
			raise ValueError("local_path cannot contain parent-directory traversal")
		return value

	@model_validator(mode="after")
	def require_source_location(self) -> "QuestionnaireSourceDocument":
		"""Require either a bundled file reference or the authoritative web URL."""
		if self.local_path is None and self.source_url is None:
			raise ValueError("A source document must include a source URL or local path")
		return self


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
	form_type: QuestionnaireFormType = Field(
		default="full",
		description="Questionnaire form length or intended administration form.",
	)
	variant_types: list[QuestionnaireVariantType] = Field(
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
	source_documents: list[QuestionnaireSourceDocument] = Field(
		default_factory=list,
		description=(
			"Version forms, validation studies, and manuals with source/licence provenance."
		),
	)
	metadata: QuestionnaireMetadata = Field(
		default_factory=QuestionnaireMetadata,
		description="Version-specific search tags, controlled terms, characteristics, and notes.",
	)
	cosmin_metrics: dict[str, Any] = Field(
		default_factory=dict,
		description="Psychometric quality metrics associated with this version.",
	)
	administration_time: str | None = Field(
		default=None,
		description="Source-reported or clearly labelled estimated completion time.",
	)
	recall_period: str | None = Field(
		default=None,
		description="Reference period respondents are asked to consider, if applicable.",
	)
	response_format: str | None = Field(
		default=None,
		description="Human-readable response mode and scale structure.",
	)
	item_structure: str | None = Field(
		default=None,
		description="Human-readable item count, subscale, or form structure summary.",
	)
	scoring_notes: str | None = Field(
		default=None,
		description=(
			"Source-grounded scoring and interpretation workflow; not a calculation engine."
		),
	)
	psychometric_summary: str | None = Field(
		default=None,
		description=(
			"Short source-grounded summary of reliability, validity, norms, or evidence limits."
		),
	)
	response_sets: dict[str, list[ResponseOption]] = Field(
		default_factory=dict,
		description="Named categorical response scales; numeric forms may define none.",
	)
	item_text_included: bool = Field(
		default=True,
		description=(
			"Whether item wording is included in this catalogue record. False is for "
			"reference records that retain discovery metadata but not source wording. "
			"This flag must not be treated as a use-permission decision."
		),
	)
	source_reported_item_count: int | None = Field(
		default=None,
		ge=1,
		description="Source-reported form length for reference records whose items are not stored.",
	)
	source_reported_dimensions: list[str] = Field(
		default_factory=list,
		description="Source-reported dimensions/subscales when item-level mapping is unavailable.",
	)
	items: list[ItemSchema] = Field(
		default_factory=list,
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
		if self.item_text_included and not self.items:
			raise ValueError("Versions with included item text must contain at least one item")
		if not self.item_text_included and self.items:
			raise ValueError("Link-only versions cannot include item wording")
		item_ids = [item.item_id for item in self.items]
		if len(item_ids) != len(set(item_ids)):
			raise ValueError("item_id values must be unique within a questionnaire version")

		# REDCap field names are treated case-insensitively to prevent collisions.
		variable_names = [item.variable_name.casefold() for item in self.items]
		if len(variable_names) != len(set(variable_names)):
			raise ValueError("variable_name values must be unique within a questionnaire version")

		for item in self.items:
			if item.response_set_ref is None:
				if item.response_mode == "categorical":
					raise ValueError(
						f"Categorical item {item.item_id!r} must reference a response set"
					)
				continue
			if item.response_set_ref not in self.response_sets:
				raise ValueError(
					f"Item {item.item_id!r} references unknown response set "
					f"{item.response_set_ref!r}"
				)
			if not self.response_sets[item.response_set_ref]:
				raise ValueError(
					f"Item {item.item_id!r} references an empty response set "
					f"{item.response_set_ref!r}"
				)

		for algorithm in self.scoring_algorithms:
			unknown_items = set(algorithm.target_items) - set(item_ids)
			if unknown_items:
				raise ValueError(
					f"Scoring algorithm {algorithm.output_variable!r} references "
					f"unknown items: {sorted(unknown_items)}"
				)
			unscored_targets = {
				item.item_id for item in self.items if not item.is_scored
			} & set(algorithm.target_items)
			if unscored_targets:
				raise ValueError(
					f"Scoring algorithm {algorithm.output_variable!r} references "
					f"unscored items: {sorted(unscored_targets)}"
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
	is_commercial: bool | None = Field(
		default=None,
		description=(
			"Whether use of this instrument is commercially restricted; None means "
			"the source status has not been established."
		),
	)
	contributors: list[QuestionnaireContributor] = Field(
		default_factory=list,
		description="Original instrument-level authors or groups, when known.",
	)
	metadata: QuestionnaireMetadata = Field(
		default_factory=QuestionnaireMetadata,
		description="Instrument-family search tags, controlled terms, and review notes.",
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
