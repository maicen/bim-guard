"""Unit tests for app.services.bsdd_semantic_mapper (candidate retrieval, no LLM call)."""

from __future__ import annotations

from app.modules.contracts import BSDDClassItem, BSDDPropertyItem
from app.services.bsdd_semantic_mapper import BsddSemanticMapper, _query_words


def _class(code: str) -> BSDDClassItem:
    return BSDDClassItem(uri=f"https://x/class/{code}", code=code, name=code, dictionary_uri="https://x")


def _prop(name: str, uri: str | None = None) -> BSDDPropertyItem:
    return BSDDPropertyItem(uri=uri or f"https://x/prop/{name}", name=name)


class FakeBsddRepo:
    """Returns whatever `search_classes`/`search_properties` is told to, per word."""

    def __init__(self, classes_by_word: dict[str, list[BSDDClassItem]] | None = None,
                 properties_by_word: dict[str, list[BSDDPropertyItem]] | None = None) -> None:
        self._classes_by_word = classes_by_word or {}
        self._properties_by_word = properties_by_word or {}

    def search_classes(self, query: str, limit: int = 10):
        return self._classes_by_word.get(query.lower(), [])[:limit]

    def search_properties(self, query: str, limit: int = 10):
        return self._properties_by_word.get(query.lower(), [])[:limit]


def test_query_words_splits_snake_and_kebab_case():
    assert _query_words("Fire_Resistance_Rating") == ["fire", "resistance", "rating"]
    assert _query_words("door-swing-angle") == ["door", "swing", "angle"]


def test_query_words_drops_short_words_and_dedupes():
    assert _query_words("Fire Of Fire") == ["fire"]  # "of" (2 chars) dropped, "fire" deduped


def test_candidate_classes_unions_across_words_and_dedupes_by_uri():
    shared = _class("IfcWall")
    repo = FakeBsddRepo(classes_by_word={
        "fire": [shared, _class("Pset_WallCommon")],
        "wall": [shared],
    })
    mapper = BsddSemanticMapper(bsdd_repo=repo)

    candidates = mapper._candidate_classes("Fire Wall")

    uris = [c.uri for c in candidates]
    assert uris.count(shared.uri) == 1  # deduped despite matching both words
    assert len(candidates) == 2


def test_candidate_classes_falls_back_to_raw_query_when_no_words_survive():
    repo = FakeBsddRepo(classes_by_word={"ab": [_class("Ab")]})  # 2-char word never reaches search
    mapper = BsddSemanticMapper(bsdd_repo=repo)

    # "ab" alone is < _MIN_WORD_LEN, so _query_words("ab") == [] and the raw
    # query itself must be used as the fallback search term instead.
    candidates = mapper._candidate_classes("ab")

    assert candidates == [_class("Ab")]


def test_candidate_properties_caps_at_max_candidates():
    # Each word's own search is capped at 10 (search_properties(..., limit=10)),
    # so the overall 25-candidate cap only bites once several words each
    # contribute distinct candidates -- three disjoint words x 10 each = 30 raw.
    repo = FakeBsddRepo(properties_by_word={
        "fire": [_prop(f"Fire{i}", uri=f"https://x/fire{i}") for i in range(10)],
        "resistance": [_prop(f"Res{i}", uri=f"https://x/res{i}") for i in range(10)],
        "rating": [_prop(f"Rating{i}", uri=f"https://x/rating{i}") for i in range(10)],
    })
    mapper = BsddSemanticMapper(bsdd_repo=repo)

    candidates = mapper._candidate_properties("Fire Resistance Rating")

    assert len(candidates) == 25


def test_candidate_classes_empty_when_nothing_matches():
    mapper = BsddSemanticMapper(bsdd_repo=FakeBsddRepo())
    assert mapper._candidate_classes("Something Nobody Has") == []
