"""Book catalog lookups (Open Library, optional Google Books) that fill in facts on verified books.

A catalog record only counts when its title and author match the book. Web-confirmed facts win;
catalogs fill the gaps, and the earliest publication year is kept.
"""

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from bookrec.models import Book
from bookrec.verify import normalize_text, normalize_title

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 6
DEFAULT_MIN_RATINGS = 10
RESULTS_PER_LOOKUP = 5
USER_AGENT = "BookFinder/0.1 (+https://github.com/swamyswamynathan123/bookrecommender)"


class CatalogRecord(BaseModel):
    source: str
    title: str
    authors: list[str] = []
    year: int | None = None
    page_count: int | None = None
    rating: float | None = None
    ratings_count: int | None = None
    cover_url: str | None = None
    link_url: str | None = None


LookupFn = Callable[[str, str], list[CatalogRecord]]


def _https(url: str | None) -> str | None:
    return url.replace("http://", "https://", 1) if url else None


def _year(value) -> int | None:
    m = re.match(r"\d{4}", str(value or ""))
    return int(m.group(0)) if m else None


def _rating(value) -> float | None:
    return round(float(value), 1) if value else None


def parse_open_library(data: dict) -> list[CatalogRecord]:
    return [
        CatalogRecord(
            source="Open Library", title=d.get("title", ""), authors=d.get("author_name") or [],
            year=d.get("first_publish_year"), page_count=d.get("number_of_pages_median"),
            rating=_rating(d.get("ratings_average")), ratings_count=d.get("ratings_count"),
            cover_url=f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg" if d.get("cover_i") else None,
            link_url=f"https://openlibrary.org{d['key']}" if d.get("key") else None,
        )
        for d in data.get("docs", [])
    ]


def parse_google_books(data: dict) -> list[CatalogRecord]:
    records = []
    for item in data.get("items", []):
        v = item.get("volumeInfo", {})
        records.append(CatalogRecord(
            source="Google Books", title=v.get("title", ""), authors=v.get("authors") or [],
            year=_year(v.get("publishedDate")), page_count=v.get("pageCount") or None,
            rating=_rating(v.get("averageRating")), ratings_count=v.get("ratingsCount"),
            cover_url=_https((v.get("imageLinks") or {}).get("thumbnail")),
            link_url=_https(v.get("previewLink") or v.get("infoLink")),
        ))
    return records


def _first_author_surname(author: str) -> str:
    first = re.split(r",| and | & |;| translated by | edited by ", normalize_text(author))[0]
    words = first.split()
    return words[-1] if words else ""


def matches(record: CatalogRecord, title: str, author: str) -> bool:
    surname = _first_author_surname(author)
    return (normalize_title(record.title) == normalize_title(title) and bool(surname)
            and any(surname in normalize_text(a).split() for a in record.authors))


def enrich_from_catalogs(book: Book, records: list[CatalogRecord], min_ratings: int = DEFAULT_MIN_RATINGS) -> Book:
    found = [r for r in records if matches(r, book.title, book.author)]
    if not found:
        return book
    updates: dict = {}
    years = [y for y in [book.year, *(r.year for r in found)] if y]
    if years:
        updates["year"] = min(years)
    if book.page_count is None:
        updates["page_count"] = next((r.page_count for r in found if r.page_count), None)
    if book.rating is None:
        # Catalog ratings come from small communities; too few ratings would mislead
        rated = next((r for r in found if r.rating and (r.ratings_count or 0) >= min_ratings), None)
        if rated:
            updates.update(rating=rated.rating, rating_source=rated.source, rating_url=rated.link_url,
                           ratings_count=rated.ratings_count)
    updates["cover_url"] = next((r.cover_url for r in found if r.cover_url), None)
    updates["google_books_url"] = next((r.link_url for r in found if r.source == "Google Books" and r.link_url), None)
    updates["open_library_url"] = next((r.link_url for r in found if r.source == "Open Library" and r.link_url), None)
    return book.model_copy(update=updates)


def make_catalog_enricher(lookups: list[LookupFn], min_ratings: int = DEFAULT_MIN_RATINGS,
                          max_workers: int = 8) -> Callable[[list[Book]], list[Book]]:
    """Look every book up in every catalog at once; a failing lookup just contributes nothing."""

    def safe(lookup: LookupFn, book: Book) -> list[CatalogRecord]:
        try:
            return lookup(book.title, book.author)
        except Exception:
            logger.warning("Catalog lookup failed for %r", book.title, exc_info=True)
            return []

    def enrich(books: list[Book]) -> list[Book]:
        if not books or not lookups:
            return books
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [[pool.submit(safe, lookup, b) for lookup in lookups] for b in books]
            return [enrich_from_catalogs(b, [r for f in fs for r in f.result()], min_ratings)
                    for b, fs in zip(books, futures)]

    return enrich


def make_open_library_lookup() -> LookupFn:
    import httpx
    from langsmith import traceable

    @traceable(run_type="tool", name="open_library_lookup")
    def lookup(title: str, author: str) -> list[CatalogRecord]:
        response = httpx.get(
            "https://openlibrary.org/search.json",
            params={"title": normalize_title(title), "author": _first_author_surname(author),
                    "limit": RESULTS_PER_LOOKUP,
                    "fields": "key,title,author_name,first_publish_year,number_of_pages_median,"
                              "ratings_average,ratings_count,cover_i"},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return parse_open_library(response.json())

    return lookup


def make_google_books_lookup(api_key: str) -> LookupFn:
    import httpx
    from langsmith import traceable

    @traceable(run_type="tool", name="google_books_lookup")
    def lookup(title: str, author: str) -> list[CatalogRecord]:
        query = f'intitle:"{normalize_title(title)}" inauthor:{_first_author_surname(author)}'
        # Key goes in a header, not the URL, so it never appears in error messages, logs or traces
        response = httpx.get("https://www.googleapis.com/books/v1/volumes",
                             params={"q": query, "maxResults": RESULTS_PER_LOOKUP},
                             headers={"X-Goog-Api-Key": api_key}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return parse_google_books(response.json())

    return lookup
