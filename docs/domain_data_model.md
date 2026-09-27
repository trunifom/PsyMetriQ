# Domain Data Model

## Design goal

Psychometric instruments are families of related but non-identical forms. One instrument may have a long and a short form, a revision, a translation, a regional or cultural adaptation, forms for different age groups, and adaptations authored by different teams. Those forms must remain distinguishable while preserving the history and evidence that connects them.

PsyMetriQ models the instrument family separately from each concrete form. A form is not assumed to be interchangeable with another form just because both share a name.

## Entity hierarchy

```text
QuestionnaireParent (instrument family)
|-- instrument-level contributors (original authorship)
|-- QuestionnaireVersion (one concrete form and language/locale)
|   |-- form type and applicable variant types
|   |-- target populations and version-specific contributors
|   |-- source citation and based-on references
|   |-- response sets
|   |-- items
|   `-- scoring algorithms
`-- additional QuestionnaireVersion records
```

Each JSON file represents one `QuestionnaireParent` and all versions stored with that instrument family. This keeps related forms together for sharing and allows local ancestry checks within the family.

## Instrument family: `QuestionnaireParent`

The parent identifies the conceptual instrument family using a stable `instrument_id` and human-readable `name_full`. It can also store construct ontology identifiers, commercial-use status, and contributors responsible for the original instrument or family.

Use one parent when forms are genuinely versions or adaptations of the same instrument. Do not merge two instruments merely because they measure a similar construct. Use `based_on` to describe derivation explicitly.

## Concrete form: `QuestionnaireVersion`

Every version has its own stable `version_id`, language, response sets, items, and scoring rules. Optional metadata makes variant distinctions explicit:

- `display_name`: label for people, such as `Adolescent Short Form`.
- `language`: language tag, independent of region, such as `de` or `en`.
- `locale`: regional context, such as `de-DE`, `de-CH`, or `en-US`.
- `form_type`: one of `full`, `short`, `long`, `screening`, or `custom`.
- `variant_types`: zero or more of `revision`, `translation`, `cultural_adaptation`, `population_adaptation`, `extension`, and `validation`. This permits, for example, a translated short form that is also culturally and population adapted.
- `target_populations`: source-reported population labels and optional minimum/maximum ages. These describe a source's intended audience; they are not clinical eligibility rules or normative claims.
- `contributors`: people or groups credited for this specific version, with roles such as author, translator, adapter, editor, reviewer, or validator.
- `publication_year`, `source_citation`, and `source_doi`: provenance for the version-specific publication or documentation.
- `based_on`: one or more `(instrument_id, version_id)` references identifying source forms.
- `metadata`: version-specific keywords, search aliases, MeSH terms, characteristics, and review notes.

The `items` list is the actual content of the concrete form. A short form must contain its own item list and scoring rules rather than inheriting a parent's item list implicitly. This makes a search result or future export unambiguous.
Each item can also have its own `QuestionnaireMetadata` for item-specific tags and discovery notes.

## Authorship and provenance

Original instrument contributors belong on `QuestionnaireParent`. People responsible for revising, translating, culturally adapting, validating, or extending a form belong on that `QuestionnaireVersion`. A person can be represented more than once when they had distinct roles in distinct versions.

Record source-reported details and distinguish unknown values from known facts. Optional fields should remain empty when a publication does not provide the information; do not infer authorship, target ages, locale, or revision history from a filename.

A `based_on` reference within the same `instrument_id` is checked for existence and cycles. A reference to another instrument family can be stored to represent cross-family adaptation, but the current validator cannot confirm that the external file exists. Resolving external references across a shared collection is a future collection-level validation feature.

## Example: translated adolescent short form

This abbreviated example shows the variant metadata. Item and response-set details are abbreviated; real records must include complete validated content.

```json
{
  "instrument_id": "demo_instrument",
  "name_full": "Synthetic Demonstration Questionnaire",
  "construct_ontology": [],
  "is_commercial": false,
  "contributors": [
    {"name": "Synthetic Original Team", "role": "author"}
  ],
  "versions": [
    {
      "version_id": "original_en_full",
      "language": "en",
      "display_name": "Original Full Form",
      "locale": "en-US",
      "form_type": "full",
      "response_sets": {},
      "items": [],
      "scoring_algorithms": []
    },
    {
      "version_id": "de_adolescent_short_v1",
      "language": "de",
      "display_name": "German Adolescent Short Form",
      "locale": "de-DE",
      "form_type": "short",
      "variant_types": [
        "translation",
        "cultural_adaptation",
        "population_adaptation"
      ],
      "target_populations": [
        {
          "group_name": "adolescents",
          "minimum_age_years": 13,
          "maximum_age_years": 17
        }
      ],
      "contributors": [
        {"name": "Synthetic Translation Team", "role": "translator"},
        {"name": "Synthetic Adaptation Team", "role": "adapter"}
      ],
      "based_on": [
        {"instrument_id": "demo_instrument", "version_id": "original_en_full"}
      ],
      "publication_year": 2024,
      "source_citation": "Synthetic example citation for schema documentation.",
      "response_sets": {},
      "items": [],
      "scoring_algorithms": []
    }
  ]
}
```

The empty lists and maps in this excerpt illustrate omitted content only; `QuestionnaireVersion` requires valid response-set and item fields under the current schema.

## Validation and identity rules

- `instrument_id` identifies an instrument family; `version_id` identifies one form within that family.
- Version IDs must be unique within a family. Item IDs must be unique within a version.
- REDCap `variable_name` values must be unique case-insensitively within a version and must satisfy the 26-character naming rule.
- Each item response-set reference and each scoring target must resolve within its version.
- Same-family `based_on` references must resolve and form an acyclic graph. External-family references are recorded but not yet resolved across files.
- Language and locale values accept a practical BCP 47 tag shape. The validator checks syntax shape, not whether a locale is a recognized or officially supported market.
- Target age bounds cannot be negative, and a minimum cannot exceed a maximum.

## Compatibility and evolution

New version metadata fields have defaults so existing Phase-1 JSON files remain readable. When adding a field, decide whether it is required for every historical record; prefer an optional structured field when older sources may not report it. Add tests for old JSON, new JSON round-trips, invalid relationships, and any migration needed before making a field mandatory.

Do not put GUI state, database details, API credentials, participant responses, or REDCap-specific configuration into these domain models. Keep them portable so the same JSON can be reviewed, shared, searched, and validated independently of the GUI or storage implementation.

## Search and Filter Metadata

`QuestionnaireMetadata` is available on the instrument family, each version, and each item. Use the narrowest scope that accurately describes a value:

- **Family metadata:** broad construct terms, common alternate names, and descriptors that apply to every form in the family.
- **Version metadata:** tags that apply only to a language, locale, form, audience, or adaptation.
- **Item metadata:** item-specific content tags, MeSH descriptors, or reviewer notes.

Its fields are:

- `keywords`: curated terms. They participate in free-text search and can be selected as exact-match filters.
- `search_aliases`: alternate instrument names, abbreviations, synonyms, and spelling variants. They participate in free-text search but are not controlled-vocabulary filters.
- `mesh_terms`: structured MeSH descriptor names and optional Unique IDs, with optional qualifiers. Verify descriptor IDs against the official MeSH source before treating them as authoritative.
- `characteristics`: searchable and filterable labels, such as `self-report`, `interviewer-administered`, or `reverse-scored-items`. Use stable, lowercase kebab-case labels within a team.
- `notes`: full-text review context. Keep notes source-based and safe to share; never store credentials, participant responses, or confidential observations in them.

Prefer existing structured fields when a concept has its own meaning: put respondent groups and ages in `target_populations`, locale in `locale`, and ontology codes in `construct_ontology` instead of duplicating those values only as keywords.

`QuestionnaireSearchFilters` combines languages, locales, form types, variant types, target populations, construct ontology codes, keywords, MeSH descriptors/IDs, characteristics, and commercial status. Values within one category are alternatives (OR); distinct categories must all match (AND). Text search can be combined with filters. Filters without text return matching items; a blank text query without active filters returns no results.

Within metadata categories, a matching family, version, or item value is sufficient. Form, language, locale, population, and commercial filters retain their proper family/version scope. Search hits preserve `QuestionnaireMetadata` as typed objects so a GUI can display provenance and tags without parsing flattened strings. Missing metadata in older JSON defaults to empty lists or `None` and does not block loading.

Example metadata payload (all values below are synthetic):

```json
{
  "keywords": ["mood", "daily functioning"],
  "search_aliases": ["synthetic wellbeing scale"],
  "mesh_terms": [
    {
      "descriptor": "Synthetic concept label",
      "descriptor_id": null,
      "qualifiers": []
    }
  ],
  "characteristics": ["self-report", "short-completion"],
  "notes": "Synthetic documentation note; replace with source-verified context."
}
```

Place this object in a model's `metadata` field. Family-level values are inherited by search/filter matching for its versions and items; version and item metadata add progressively narrower terms without changing the portable JSON hierarchy.
