from bookrec.models import SearchResult
from bookrec.search import run_queries
from tests.fakes import FakeSearch


def r(url: str) -> SearchResult:
    return SearchResult(url=url, title="t", content="c")


def test_run_queries_respects_remaining_budget():
    fake = FakeSearch({"a": [r("u1")], "b": [r("u2")], "c": [r("u3")]})
    results, used = run_queries(fake, ["a", "b", "c"], max_results=3, remaining=2)
    assert used == 2 and fake.queries == ["a", "b"] and [x.url for x in results] == ["u1", "u2"]


def test_run_queries_dedupes_by_url():
    fake = FakeSearch({"a": [r("u1")], "b": [r("u1"), r("u2")]})
    results, used = run_queries(fake, ["a", "b"], 3, 8)
    assert used == 2 and [x.url for x in results] == ["u1", "u2"]


def test_zero_remaining_makes_no_calls():
    fake = FakeSearch({})
    assert run_queries(fake, ["a"], 3, 0) == ([], 0) and fake.queries == []


def test_make_tavily_search_maps_results(monkeypatch):
    import tavily
    from bookrec.search import make_tavily_search

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, query, max_results, search_depth):
            return {"results": [{"url": "u1", "title": "T", "content": "C"}, {"title": "no url"}]}

    monkeypatch.setattr(tavily, "TavilyClient", FakeClient)
    assert make_tavily_search("k")("q", 3) == [SearchResult(url="u1", title="T", content="C")]
