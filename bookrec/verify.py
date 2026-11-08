"""Grounding checks: keep only what the search results actually back up."""

import re

from bookrec.models import Book, BookRequest, SearchResult

MAX_EXCERPT_CHARS = 300

_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"})


def normalize_text(s: str) -> str:
    s = s.casefold().translate(_QUOTES).replace("…", " ").replace("...", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(title: str) -> str:
    return re.split(r"[:(]", normalize_text(title), maxsplit=1)[0].strip()


def _loose(s: str) -> str:
    """Normalized text without double quotes or trailing punctuation, for excerpt matching."""
    return re.sub(r"\s+", " ", normalize_text(s).replace('"', " ")).strip(" .,;:!?")


def _rating_forms(rating: float) -> set[str]:
    base = f"{rating:.2f}".rstrip("0").rstrip(".")
    forms = {base}
    if "." not in base:
        forms |= {f"{base}.0", f"{base}.00"}
    elif len(base.split(".")[1]) == 1:
        forms.add(base + "0")
    return forms


def rating_is_backed(rating: float, text: str) -> bool:
    for form in _rating_forms(rating):
        pattern = r"(?<![\d.,])" + re.escape(form).replace(r"\.", "[.,]") + r"(?![\d])"
        if re.search(pattern, text):
            return True
    return False


def _number_in(n: int, text: str) -> bool:
    return re.search(rf"(?<!\d){n}(?!\d)", text) is not None


def verify_books(
    books: list[Book],
    results: list[SearchResult],
    request: BookRequest,
    exclude_titles: set[str],
    max_books: int,
    already: list[Book] = [],
) -> list[Book]:
    url_map = {r.url: r for r in results}
    seen = set(exclude_titles) | {normalize_title(b.title) for b in already}
    kept: list[Book] = []

    for book in books:
        if book.source_url not in url_map:
            continue
        key = normalize_title(book.title)
        if not key or key in seen:
            continue
        updates: dict = {}

        rating_src = url_map.get(book.rating_url or "")
        if book.rating is None or not rating_src or not rating_is_backed(book.rating, rating_src.content):
            updates.update(rating=None, rating_source=None, rating_url=None)

        review_src = url_map.get(book.review_url or "")
        excerpt = book.review_excerpt or ""
        if (not excerpt or not review_src or len(excerpt) > MAX_EXCERPT_CHARS
                or _loose(excerpt) not in _loose(review_src.content)):
            updates.update(review_excerpt=None, review_source_name=None, review_url=None)

        mentioning = [r.content for r in results if key in normalize_text(r.content)]
        for field in ("page_count", "year"):
            value = getattr(book, field)
            if value is not None and not any(_number_in(value, text) for text in mentioning):
                updates[field] = None

        book = book.model_copy(update=updates)
        if request.max_pages and (book.page_count is None or book.page_count > request.max_pages):
            continue
        if request.min_year and (book.year is None or book.year < request.min_year):
            continue
        if request.max_year and (book.year is None or book.year > request.max_year):
            continue

        seen.add(key)
        kept.append(book)

    return (list(already) + kept)[:max_books]
