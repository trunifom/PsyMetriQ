"""Tests for the construct-similarity check; never loads a real embedding model."""

from pathlib import Path

import pytest

from schemas.questionnaire_schema import (
    QuestionnaireMetadata,
    QuestionnaireParent,
    QuestionnaireVersion,
)
from src.core import nlp_engine
from src.core.nlp_engine import (
    NLPEngineError,
    build_construct_summaries,
    find_similar_constructs,
)


def _link_only_family(
    instrument_id: str, *, name_full: str, constructs: list[str], keywords: list[str] | None = None
) -> QuestionnaireParent:
    return QuestionnaireParent(
        instrument_id=instrument_id,
        name_full=name_full,
        construct_ontology=constructs,
        is_commercial=None,
        metadata=QuestionnaireMetadata(keywords=keywords or []),
        versions=[
            QuestionnaireVersion(
                version_id="v1",
                language="en",
                item_text_included=False,
                source_reported_item_count=10,
            )
        ],
    )


def _bare_family(instrument_id: str) -> QuestionnaireParent:
    """A family whose name_full is whitespace-only, so its combined text strips to empty.

    ``name_full`` still satisfies the schema's ``min_length=1`` (a single
    space has length 1), so this is a real, schema-valid edge case, not an
    invalid fixture.
    """
    return QuestionnaireParent(
        instrument_id=instrument_id,
        name_full=" ",
        is_commercial=None,
        versions=[
            QuestionnaireVersion(
                version_id="v1",
                language="en",
                item_text_included=False,
                source_reported_item_count=1,
            )
        ],
    )


class _FakeEmbedder:
    """Deterministic stand-in for a real sentence-transformers model."""

    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self.vectors_by_text = vectors_by_text
        self.received: list[str] | None = None

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.received = texts
        return [self.vectors_by_text[text] for text in texts]


def test_build_construct_summaries_combines_name_constructs_and_keywords() -> None:
    family = _link_only_family(
        "demo", name_full="Demo Scale", constructs=["anxiety"], keywords=["worry", "fear"]
    )

    summaries = build_construct_summaries([(family, Path("demo.json"))])

    assert len(summaries) == 1
    assert summaries[0].instrument_id == "demo"
    assert "Demo Scale" in summaries[0].text
    assert "anxiety" in summaries[0].text
    assert "worry" in summaries[0].text


def test_find_similar_constructs_returns_pairs_at_or_above_threshold() -> None:
    family_a = _link_only_family("a", name_full="Depression Scale A", constructs=["depression"])
    family_b = _link_only_family("b", name_full="Depression Scale B", constructs=["depression"])
    family_c = _link_only_family("c", name_full="Physical Activity Scale", constructs=["exercise"])
    text_a = build_construct_summaries([(family_a, Path("a.json"))])[0].text
    text_b = build_construct_summaries([(family_b, Path("b.json"))])[0].text
    text_c = build_construct_summaries([(family_c, Path("c.json"))])[0].text
    embedder = _FakeEmbedder(
        {
            text_a: [1.0, 0.0],
            text_b: [0.99, 0.01],
            text_c: [0.0, 1.0],
        }
    )

    matches = find_similar_constructs(
        [(family_a, Path("a.json")), (family_b, Path("b.json")), (family_c, Path("c.json"))],
        threshold=0.9,
        embedding_function=embedder,
    )

    assert len(matches) == 1
    assert {matches[0].instrument_a, matches[0].instrument_b} == {"a", "b"}
    assert matches[0].similarity > 0.9


def test_find_similar_constructs_sorts_descending_and_respects_max_results() -> None:
    families = [
        _link_only_family(f"f{i}", name_full=f"Scale {i}", constructs=["shared_construct"])
        for i in range(4)
    ]
    records = [(family, Path(f"{family.instrument_id}.json")) for family in families]
    texts = [build_construct_summaries([record])[0].text for record in records]
    # All identical vectors: every pair has similarity 1.0, giving C(4,2)=6 matches.
    embedder = _FakeEmbedder({text: [1.0, 0.0] for text in texts})

    matches = find_similar_constructs(
        records, threshold=0.5, embedding_function=embedder, max_results=3
    )

    assert len(matches) == 3
    assert all(match.similarity == pytest.approx(1.0) for match in matches)


def test_find_similar_constructs_returns_empty_for_fewer_than_two_records() -> None:
    family = _link_only_family("solo", name_full="Solo Scale", constructs=["x"])

    matches = find_similar_constructs(
        [(family, Path("solo.json"))], embedding_function=_FakeEmbedder({})
    )

    assert matches == []


def test_find_similar_constructs_skips_families_with_no_construct_text() -> None:
    bare = _bare_family("bare")
    family = _link_only_family("demo", name_full="Demo Scale", constructs=["anxiety"])
    text = build_construct_summaries([(family, Path("demo.json"))])[0].text
    embedder = _FakeEmbedder({text: [1.0, 0.0]})

    matches = find_similar_constructs(
        [(bare, Path("bare.json")), (family, Path("demo.json"))],
        threshold=0.5,
        embedding_function=embedder,
    )

    # Only one family has usable text, so find_similar_constructs never even
    # has to call the embedder -- there aren't two summaries left to compare.
    assert matches == []
    assert embedder.received is None


def test_find_similar_constructs_raises_on_mismatched_vector_count() -> None:
    family_a = _link_only_family("a", name_full="A", constructs=["x"])
    family_b = _link_only_family("b", name_full="B", constructs=["y"])

    def broken_embedder(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0]]  # one vector for two texts

    with pytest.raises(NLPEngineError):
        find_similar_constructs(
            [(family_a, Path("a.json")), (family_b, Path("b.json"))],
            embedding_function=broken_embedder,
        )


def test_default_embedding_function_wraps_a_missing_dependency_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "sentence_transformers":
            raise ImportError("no module named sentence_transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(NLPEngineError, match="not installed"):
        nlp_engine._default_embedding_function()


def test_find_similar_constructs_uses_the_default_embedder_when_none_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family_a = _link_only_family("a", name_full="A", constructs=["x"])
    family_b = _link_only_family("b", name_full="B", constructs=["y"])
    called: dict[str, bool] = {}

    def fake_default_embedding_function(model_name: str = nlp_engine.DEFAULT_MODEL_NAME):
        called["used"] = True

        def embed(texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        return embed

    monkeypatch.setattr(nlp_engine, "_default_embedding_function", fake_default_embedding_function)

    find_similar_constructs([(family_a, Path("a.json")), (family_b, Path("b.json"))])

    assert called.get("used") is True
