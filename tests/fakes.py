"""Test doubles for the LLM and web search. Tests never call real APIs."""

from bookrec.models import Book, BookRequest, Candidate, SearchResult


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


class FakeLLM:
    """Scripted BookLLM. `books` holds one list per select_books call, consumed in order."""

    def __init__(self, request: BookRequest, candidates: list[Candidate] | None = None,
                 books: list[list[Book]] | None = None):
        self.request = request
        self.candidates = candidates or []
        self.books = list(books or [])
        self.parse_messages: list[str] = []
        self.parse_histories: list[list] = []
        self.select_excludes: list[list[str]] = []

    def parse_request(self, history, message: str) -> BookRequest:
        self.parse_messages.append(message)
        self.parse_histories.append(list(history))
        return self.request

    def extract_candidates(self, request, results, exclude_titles, limit) -> list[Candidate]:
        return self.candidates[:limit]

    def select_books(self, request, results, exclude_titles, count) -> list[Book]:
        self.select_excludes.append(list(exclude_titles))
        return self.books.pop(0)[:count] if self.books else []
