"""Semantic construct-similarity check across the catalog (the jingle-jangle problem).

The "jingle" fallacy is two different constructs sharing one name; "jangle"
is one construct scattered across differently named instruments. This module
embeds each instrument family's construct-level text (name, construct
ontology, description, keywords) with a sentence-embedding model and reports
ranked candidate pairs whose embeddings are highly similar, so a human
reviewer can check whether two instruments are actually measuring the same
thing.

This never merges, deduplicates, renames, or removes anything automatically.
A high similarity score is a prompt for human review, not a redundancy
finding on its own: two genuinely distinct, well-validated constructs can
still describe themselves in similar language.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from schemas.questionnaire_schema import QuestionnaireParent

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class NLPEngineError(RuntimeError):
    """Raised when embeddings cannot be computed (missing dependency, model load failure)."""


class EmbeddingFunction(Protocol):
    """A batch text-to-vector function; ``_default_embedding_function`` wraps a real model."""

    def __call__(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class InstrumentConstructSummary:
    """The text one instrument family contributes to the similarity check."""

    instrument_id: str
    name_full: str
    text: str


@dataclass(frozen=True)
class InstrumentMatch:
    """One catalog instrument ranked against a free-text research query."""

    instrument_id: str
    name_full: str
    similarity: float


@dataclass(frozen=True)
class ConstructSimilarityMatch:
    """One candidate construct overlap between two different instrument families."""

    instrument_a: str
    instrument_b: str
    name_a: str
    name_b: str
    similarity: float


def _construct_summary_text(family: QuestionnaireParent) -> str:
    """Build one instrument's construct-level text from documented, non-item fields.

    Deliberately excludes item wording: this compares what instruments claim
    to measure, not their exact phrasing, and never touches restricted item
    text for reference-only (link-only) catalog records.
    """
    parts = [family.name_full, *family.construct_ontology]
    if family.metadata.description:
        parts.append(family.metadata.description)
    if family.metadata.measurement_rationale:
        parts.append(family.metadata.measurement_rationale)
    if family.metadata.intended_use:
        parts.append(family.metadata.intended_use)
    parts.extend(family.metadata.keywords)
    parts.extend(family.metadata.search_aliases)
    return ". ".join(part.strip() for part in parts if part and part.strip())


def build_construct_summaries(
    catalog_records: list[tuple[QuestionnaireParent, Path]],
) -> list[InstrumentConstructSummary]:
    """Collect one summary per instrument family that has enough text to embed."""
    summaries: list[InstrumentConstructSummary] = []
    for family, _path in catalog_records:
        text = _construct_summary_text(family)
        if not text:
            continue
        summaries.append(
            InstrumentConstructSummary(
                instrument_id=family.instrument_id, name_full=family.name_full, text=text
            )
        )
    return summaries


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=True))
    norm_a = sum(a * a for a in vector_a) ** 0.5
    norm_b = sum(b * b for b in vector_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _default_embedding_function(model_name: str = DEFAULT_MODEL_NAME) -> EmbeddingFunction:
    """Load a local sentence-transformers model; imported lazily, only when actually used.

    The first call for a given model name downloads its weights from the
    Hugging Face Hub if not already cached locally, which requires network
    access; callers that cannot assume that should inject their own
    ``embedding_function`` instead (see ``find_similar_constructs``).
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise NLPEngineError(
            "sentence-transformers is not installed; run `pip install -r requirements.txt`"
        ) from error
    try:
        model = SentenceTransformer(model_name)
    except Exception as error:
        raise NLPEngineError(
            f"Could not load sentence-transformers model {model_name!r} "
            f"({type(error).__name__}); it may need to be downloaded once with network access"
        ) from None

    def embed(texts: list[str]) -> list[list[float]]:
        return model.encode(list(texts), normalize_embeddings=True).tolist()

    return embed


def find_matching_instruments(
    query: str,
    catalog_records: list[tuple[QuestionnaireParent, Path]],
    *,
    embedding_function: EmbeddingFunction | None = None,
    max_results: int = 15,
) -> list[InstrumentMatch]:
    """Rank catalog instruments by semantic similarity to a free-text research query.

    Uses the same construct-level text and embedding model as
    ``find_similar_constructs`` -- name, construct ontology, description,
    keywords -- never item wording. Returns the top ``max_results`` matches
    sorted by descending similarity regardless of score: this is a ranking
    for a human to scan, not a redundancy threshold, so a caller decides how
    to present a weak match rather than having it silently dropped.
    """
    normalized_query = query.strip()
    if not normalized_query:
        return []
    summaries = build_construct_summaries(catalog_records)
    if not summaries:
        return []
    embed = embedding_function or _default_embedding_function()
    vectors = embed([normalized_query, *(summary.text for summary in summaries)])
    if len(vectors) != len(summaries) + 1:
        raise NLPEngineError("Embedding function returned a different number of vectors than texts")

    query_vector = vectors[0]
    matches = [
        InstrumentMatch(
            instrument_id=summary.instrument_id,
            name_full=summary.name_full,
            similarity=round(_cosine_similarity(query_vector, vector), 4),
        )
        for summary, vector in zip(summaries, vectors[1:], strict=True)
    ]
    matches.sort(key=lambda match: match.similarity, reverse=True)
    return matches[:max_results]


def find_similar_constructs(
    catalog_records: list[tuple[QuestionnaireParent, Path]],
    *,
    threshold: float = 0.75,
    embedding_function: EmbeddingFunction | None = None,
    max_results: int = 50,
) -> list[ConstructSimilarityMatch]:
    """Return ranked candidate construct-overlap pairs at or above ``threshold``.

    ``threshold`` is a cosine similarity in [-1, 1] (in practice normalized
    sentence embeddings mostly fall in [0, 1]); higher means more similar.
    Pass ``embedding_function`` to use an already-loaded model or a fake for
    tests; omitting it loads the default local sentence-transformers model,
    which may need a one-time network download.
    """
    summaries = build_construct_summaries(catalog_records)
    if len(summaries) < 2:
        return []
    embed = embedding_function or _default_embedding_function()
    vectors = embed([summary.text for summary in summaries])
    if len(vectors) != len(summaries):
        raise NLPEngineError("Embedding function returned a different number of vectors than texts")

    matches: list[ConstructSimilarityMatch] = []
    for i in range(len(summaries)):
        for j in range(i + 1, len(summaries)):
            similarity = _cosine_similarity(vectors[i], vectors[j])
            if similarity >= threshold:
                matches.append(
                    ConstructSimilarityMatch(
                        instrument_a=summaries[i].instrument_id,
                        instrument_b=summaries[j].instrument_id,
                        name_a=summaries[i].name_full,
                        name_b=summaries[j].name_full,
                        similarity=round(similarity, 4),
                    )
                )
    matches.sort(key=lambda match: match.similarity, reverse=True)
    return matches[:max_results]
