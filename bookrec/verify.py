"""Grounding checks: keep only what the search results actually back up.

Facts about a book (its existence, rating, review, page count, year) must appear in a search
result *near the book's title*, so a list page can't lend one book's numbers to another.
"""

import re
from urllib.parse import urlparse

from bookrec.models import Book, BookRequest, SearchResult

MAX_EXCERPT_CHARS = 300
MIN_EXCERPT_CHARS = 20
MIN_EXCERPT_WORDS = 4
TITLE_WINDOW_CHARS = 150

_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"})
_TITLE_CUTS = re.compile(r":|\(| - | — | – | by ")
_LEADING_ARTICLE = re.compile(r"^(the|a|an) ")
_RATING_AFTER = re.compile(r"\s*(/\s*5(?!\d)|out of 5(?!\d)|of 5(?!\d)|stars?\b|avg|average|rating|[\d,]+\s*ratings)")
_RATING_BEFORE = re.compile(r"(rated|rating|avg|average|score|scored)\W{0,6}$")
_OTHER_SCALE = re.compile(r"\s*(/\s*|out of |of )(?!5(?!\d))\d")
_PAGES_AFTER = re.compile(r"\s*(pages|page|pp)\b")
_NEGATION = re.compile(r"(\bnot|n't|\bnever|\bno)\s*$")


def normalize_text(s: str) -> str:
    s = s.casefold().translate(_QUOTES).replace("…", " ").replace("...", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(title: str) -> str:
    title = _TITLE_CUTS.split(normalize_text(title), maxsplit=1)[0].strip()
    return _LEADING_ARTICLE.sub("", title).strip()


def _loose(s: str) -> str:
    """Normalized text without double quotes or trailing punctuation, for excerpt matching."""
    return re.sub(r"\s+", " ", normalize_text(s).replace('"', " ")).strip(" .,;:!?")


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _title_windows(key: str, result: SearchResult) -> list[str]:
    """Text around each mention of the title in a result (empty if it never mentions it).

    A page whose own title starts with the book's title is about that book, so all of it counts.
    """
    text = normalize_text(f"{result.title} {result.content}")
    if normalize_title(result.title).startswith(key):
        return [text]
    return [
        text[max(0, m.start() - TITLE_WINDOW_CHARS): m.end() + TITLE_WINDOW_CHARS]
        for m in re.finditer(rf"(?<!\w){re.escape(key)}(?!\w)", text)
    ]


def _rating_forms(rating: float) -> set[str]:
    base = f"{rating:.2f}".rstrip("0").rstrip(".")
    forms = {base}
    if "." not in base:
        forms |= {f"{base}.0", f"{base}.00"}
    elif len(base.split(".")[1]) == 1:
        forms.add(base + "0")
    return forms


def rating_is_backed(rating: float, text: str) -> bool:
    """True if the rating appears as a rating (with rating context, on a 5-point scale)."""
    text = text.casefold()
    for form in _rating_forms(rating):
        pattern = r"(?<![\w$.,])" + re.escape(form).replace(r"\.", "[.,]") + r"(?![.,]?\d)"
        for m in re.finditer(pattern, text):
            after = text[m.end(): m.end() + 20]
            before = text[max(0, m.start() - 25): m.start()]
            if _OTHER_SCALE.match(after):
                continue
            if _RATING_AFTER.match(after) or _RATING_BEFORE.search(before):
                return True
    return False


def _excerpt_is_backed(excerpt: str, windows_text: str) -> bool:
    loose = _loose(excerpt)
    if len(loose) < MIN_EXCERPT_CHARS or len(loose.split()) < MIN_EXCERPT_WORDS:
        return False
    haystack = _loose(windows_text)
    for m in re.finditer(rf"(?<!\w){re.escape(loose)}(?!\w)", haystack):
        if not _NEGATION.search(haystack[max(0, m.start() - 10): m.start()]):
            return True
    return False


def _pages_backed(n: int, windows: list[str]) -> bool:
    for text in windows:
        for m in re.finditer(rf"(?<!\d){n}(?!\d)", text):
            if _PAGES_AFTER.match(text[m.end():]):
                return True
    return False


def _number_backed(n: int, windows: list[str]) -> bool:
    return any(re.search(rf"(?<!\d){n}(?!\d)", text) for text in windows)


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
        key = normalize_title(book.title)
        source = url_map.get(book.source_url)
        if not key or key in seen or not source or not _title_windows(key, source):
            continue
        updates: dict = {}

        rating_src = url_map.get(book.rating_url or "")
        rating_windows = _title_windows(key, rating_src) if rating_src else []
        if book.rating is not None and any(rating_is_backed(book.rating, w) for w in rating_windows):
            updates["rating_source"] = _domain(book.rating_url)
        else:
            updates.update(rating=None, rating_source=None, rating_url=None)

        review_src = url_map.get(book.review_url or "")
        excerpt = book.review_excerpt or ""
        if (review_src and len(excerpt) <= MAX_EXCERPT_CHARS
                and _excerpt_is_backed(excerpt, normalize_text(f"{review_src.title} {review_src.content}"))
                and _title_windows(key, review_src)):
            updates["review_source_name"] = _domain(book.review_url)
        else:
            updates.update(review_excerpt=None, review_source_name=None, review_url=None)

        windows = [w for r in results for w in _title_windows(key, r)]
        if book.page_count is not None and not _pages_backed(book.page_count, windows):
            updates["page_count"] = None
        if book.year is not None and not _number_backed(book.year, windows):
            updates["year"] = None

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
