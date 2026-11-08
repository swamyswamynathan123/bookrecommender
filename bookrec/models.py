"""Data shapes shared by search, LLM, verification and rendering."""

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    url: str
    title: str
    content: str


class BookRequest(BaseModel):
    is_book_request: bool
    topic: str = ""
    soft_constraints: list[str] = Field(default_factory=list)
    like_title: str | None = None
    max_pages: int | None = None
    min_year: int | None = None
    max_year: int | None = None


class Candidate(BaseModel):
    title: str
    author: str


class Book(BaseModel):
    title: str
    author: str
    description: str
    why_it_fits: str
    source_url: str
    rating: float | None = None
    rating_source: str | None = None
    rating_url: str | None = None
    review_excerpt: str | None = None
    review_source_name: str | None = None
    review_url: str | None = None
    page_count: int | None = None
    year: int | None = None
