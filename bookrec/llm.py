"""LLM interface used by the graph, and its OpenAI implementation."""

from typing import Protocol

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from bookrec.models import Book, BookRequest, Candidate, SearchResult


class BookLLM(Protocol):
    def parse_request(self, history: list[BaseMessage], message: str) -> BookRequest: ...

    def extract_candidates(self, request: BookRequest, results: list[SearchResult],
                           exclude_titles: list[str], limit: int) -> list[Candidate]: ...

    def select_books(self, request: BookRequest, results: list[SearchResult],
                     exclude_titles: list[str], count: int) -> list[Book]: ...


class BookList(BaseModel):
    books: list[Book]


class CandidateList(BaseModel):
    candidates: list[Candidate]


PARSE_SYSTEM = """You turn a visitor's chat message into a structured book search request.
- Set is_book_request=false if the message is not about finding or refining book recommendations.
- On a refinement ("shorter ones", "more modern", "more like the second one"), carry the previous
  topic forward from the conversation and add the new constraints.
- Resolve references like "the second one" to the actual book title from the conversation (like_title).
- Hard constraints go in max_pages / min_year / max_year. Everything else ("practical",
  "beginner-friendly") goes in soft_constraints."""


def format_results(results: list[SearchResult], max_chars_each: int = 1500) -> str:
    blocks = [
        f"[{i}]\nURL: {r.url}\nTITLE: {r.title}\nCONTENT: {r.content[:max_chars_each]}"
        for i, r in enumerate(results, start=1)
    ]
    return "\n\n".join(blocks)


def _describe_request(request: BookRequest) -> str:
    parts = [f"Topic: {request.topic}"]
    if request.soft_constraints:
        parts.append(f"Preferences: {', '.join(request.soft_constraints)}")
    if request.like_title:
        parts.append(f"Similar to: {request.like_title}")
    if request.max_pages:
        parts.append(f"At most {request.max_pages} pages")
    if request.min_year:
        parts.append(f"Published in or after {request.min_year}")
    if request.max_year:
        parts.append(f"Published in or before {request.max_year}")
    return "\n".join(parts)


def _exclusions(exclude_titles: list[str]) -> str:
    return ", ".join(exclude_titles) if exclude_titles else "(none)"


def candidates_prompt(request: BookRequest, results: list[SearchResult],
                      exclude_titles: list[str], limit: int) -> str:
    return f"""From the search results below, list up to {limit} real books that best match the request.
Only list books that are named in the results. Never list any of these titles: {_exclusions(exclude_titles)}.

REQUEST
{_describe_request(request)}

SEARCH RESULTS
{format_results(results)}"""


def select_prompt(request: BookRequest, results: list[SearchResult],
                  exclude_titles: list[str], count: int) -> str:
    return f"""Choose up to {count} books for the request below, using ONLY the search results.

Rules:
- Only choose books that are named in the search results. Never choose any of these titles: {_exclusions(exclude_titles)}.
- source_url must be the URL of a result that names the book.
- rating / rating_source / rating_url: only if a result states the book's rating; rating_url is that result's URL. Otherwise leave them empty.
- review_excerpt: copy a short reader or critic opinion verbatim from a result (at most 300 characters), with review_source_name (the site) and review_url (that result's URL). Otherwise leave them empty.
- page_count and year: only if a result states them. Otherwise leave them empty.
- description: 2-3 sentences. why_it_fits: one sentence tied to the request.
- Honour the preferences and the "similar to" book, and respect every hard limit.

REQUEST
{_describe_request(request)}

SEARCH RESULTS
{format_results(results)}"""


class OpenAIBookLLM:
    def __init__(self, model: str, api_key: str):
        from langchain_openai import ChatOpenAI

        self.chat = ChatOpenAI(model=model, api_key=api_key, temperature=0)

    def parse_request(self, history: list[BaseMessage], message: str) -> BookRequest:
        llm = self.chat.with_structured_output(BookRequest)
        return llm.invoke([SystemMessage(PARSE_SYSTEM), *history, HumanMessage(message)])

    def extract_candidates(self, request: BookRequest, results: list[SearchResult],
                           exclude_titles: list[str], limit: int) -> list[Candidate]:
        llm = self.chat.with_structured_output(CandidateList)
        out = llm.invoke(candidates_prompt(request, results, exclude_titles, limit))
        return out.candidates[:limit]

    def select_books(self, request: BookRequest, results: list[SearchResult],
                     exclude_titles: list[str], count: int) -> list[Book]:
        llm = self.chat.with_structured_output(BookList)
        out = llm.invoke(select_prompt(request, results, exclude_titles, count))
        return out.books[:count]
