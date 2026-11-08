"""Test doubles for the LLM and web search. Tests never call real APIs."""

from bookrec.models import SearchResult


class FakeSearch:
    def __init__(self, responses: dict[str, list[SearchResult]], raises: Exception | None = None):
        self.responses = responses
        self.raises = raises
        self.queries: list[str] = []

    def __call__(self, query: str, max_results: int) -> list[SearchResult]:
        self.queries.append(query)
        if self.raises:
            raise self.raises
        for key, results in self.responses.items():
            if key in query:
                return list(results)
        return []
