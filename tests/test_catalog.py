from bookrec.catalog import (CatalogRecord, enrich_from_catalogs, make_catalog_enricher, matches,
                             parse_google_books, parse_open_library)
from bookrec.models import Book

OL_JSON = {"docs": [{
    "key": "/works/OL20157096W", "title": "How to Think Like a Roman Emperor",
    "author_name": ["Donald Robertson"], "first_publish_year": 2019, "number_of_pages_median": 304,
    "ratings_average": 4.8333335, "ratings_count": 6, "cover_i": 8802189}]}

GB_JSON = {"items": [{"volumeInfo": {
    "title": "How to Think Like a Roman Emperor", "subtitle": "The Stoic Philosophy of Marcus Aurelius",
    "authors": ["Donald J. Robertson"], "publishedDate": "2019-04-02", "pageCount": 288,
    "averageRating": 4.5, "ratingsCount": 31,
    "imageLinks": {"thumbnail": "http://books.google.com/books/content?id=x&zoom=1"},
    "previewLink": "http://books.google.com/books?id=x&hl=&source=gbs_api",
    "infoLink": "https://books.google.com/books?id=x"}}]}


def book(**kw) -> Book:
    base = dict(title="How to Think Like a Roman Emperor: The Stoic Philosophy of Marcus Aurelius",
                author="Donald J. Robertson", description="d", why_it_fits="w", source_url="https://s")
    base.update(kw)
    return Book(**base)


def rec(**kw) -> CatalogRecord:
    base = dict(source="Open Library", title="How to Think Like a Roman Emperor", authors=["Donald Robertson"],
                link_url="https://openlibrary.org/works/OL20157096W")
    base.update(kw)
    return CatalogRecord(**base)


def test_parse_open_library():
    [r] = parse_open_library(OL_JSON)
    assert (r.source, r.year, r.page_count, r.rating, r.ratings_count) == ("Open Library", 2019, 304, 4.8, 6)
    assert r.cover_url == "https://covers.openlibrary.org/b/id/8802189-M.jpg"
    assert r.link_url == "https://openlibrary.org/works/OL20157096W"


def test_parse_google_books():
    [r] = parse_google_books(GB_JSON)
    assert (r.source, r.year, r.page_count, r.rating, r.ratings_count) == ("Google Books", 2019, 288, 4.5, 31)
    assert r.cover_url.startswith("https://") and r.link_url.startswith("https://")


def test_parse_handles_missing_fields():
    assert parse_open_library({}) == [] and parse_google_books({"totalItems": 0}) == []
    [r] = parse_google_books({"items": [{"volumeInfo": {"title": "X", "publishedDate": "abc"}}]})
    assert (r.year, r.page_count, r.rating, r.cover_url) == (None, None, None, None)


def test_matches_title_and_author_surname():
    assert matches(rec(), book().title, book().author)
    assert not matches(rec(title="How to Be a Stoic"), book().title, book().author)
    assert not matches(rec(authors=["Ryan Holiday"]), book().title, book().author)
    assert matches(rec(title="The Daily Stoic", authors=["Ryan Holiday"]),
                   "The Daily Stoic", "Ryan Holiday and Stephen Hanselman")
    assert not matches(rec(authors=[]), book().title, book().author)


def test_enrich_fills_missing_facts_and_links():
    gb = rec(source="Google Books", authors=["Donald J. Robertson"], year=2019, page_count=288,
             rating=4.5, ratings_count=31, cover_url="https://gb/cover", link_url="https://gb/link")
    ol = rec(year=2019, page_count=304, rating=4.8, ratings_count=6, cover_url="https://ol/cover")
    out = enrich_from_catalogs(book(), [gb, ol])
    assert (out.page_count, out.year, out.cover_url) == (288, 2019, "https://gb/cover")
    assert (out.rating, out.rating_source, out.rating_url, out.ratings_count) == (4.5, "Google Books", "https://gb/link", 31)
    assert (out.google_books_url, out.open_library_url) == ("https://gb/link", "https://openlibrary.org/works/OL20157096W")


def test_enrich_keeps_web_rating_and_pages():
    out = enrich_from_catalogs(book(rating=4.2, rating_source="goodreads.com", rating_url="https://g", page_count=300),
                               [rec(rating=4.8, ratings_count=6, page_count=304)])
    assert (out.rating, out.rating_source, out.page_count) == (4.2, "goodreads.com", 300)


def test_enrich_uses_earliest_year():
    out = enrich_from_catalogs(book(title="Letters from a Stoic", author="Seneca", year=2018),
                               [rec(title="Letters from a Stoic", authors=["Seneca"], year=1969)])
    assert out.year == 1969


def test_enrich_ignores_non_matching_and_unrated():
    out = enrich_from_catalogs(book(), [rec(title="Other Book", page_count=99, rating=5.0, ratings_count=9),
                                        rec(rating=3.0, ratings_count=0)])
    assert (out.page_count, out.rating, out.open_library_url) == (None, None, "https://openlibrary.org/works/OL20157096W")


def test_enricher_survives_failing_lookup():
    def broken(title, author):
        raise RuntimeError("down")

    def works(title, author):
        return [rec(page_count=304)]

    [out] = make_catalog_enricher([broken, works])([book()])
    assert out.page_count == 304
    assert make_catalog_enricher([broken])([book()]) == [book()]


def test_catalog_rating_needs_enough_ratings():
    few = enrich_from_catalogs(book(), [rec(rating=2.4, ratings_count=7)], min_ratings=10)
    enough = enrich_from_catalogs(book(), [rec(rating=3.9, ratings_count=32)], min_ratings=10)
    assert few.rating is None and (enough.rating, enough.ratings_count) == (3.9, 32)
    out = make_catalog_enricher([lambda t, a: [rec(rating=2.4, ratings_count=7)]], min_ratings=5)([book()])
    assert out[0].rating == 2.4
