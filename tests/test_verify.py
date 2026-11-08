from bookrec.models import Book, BookRequest, SearchResult
from bookrec.verify import rating_is_backed, verify_books

SRC = "https://src"
REQ = BookRequest(is_book_request=True, topic="stoicism")


def book(**overrides) -> Book:
    fields = dict(
        title="Meditations", author="Marcus Aurelius", description="d", why_it_fits="w",
        source_url=SRC, rating=4.3, rating_source="Goodreads", rating_url=SRC,
        review_excerpt="a wonderful read", review_source_name="Goodreads", review_url=SRC,
    )
    fields.update(overrides)
    return Book(**fields)


def results(content="Meditations by Marcus Aurelius. 4.30 avg rating. A wonderful read.") -> list[SearchResult]:
    return [SearchResult(url=SRC, title="t", content=content)]


def verify(books, res=None, request=REQ, exclude=frozenset(), max_books=5, already=None):
    return verify_books(books, res if res is not None else results(), request, set(exclude),
                        max_books=max_books, already=already or [])


def test_drops_book_without_known_source():
    assert verify([book(source_url="https://other")]) == []


def test_rating_formats():
    assert rating_is_backed(4.3, "4.30 avg rating")
    assert rating_is_backed(4.3, "rated 4,3/5")
    assert rating_is_backed(4.35, "score 4.35 of 5")
    assert not rating_is_backed(4.3, "page 14.3")
    assert not rating_is_backed(4.3, "rated 4.4")


def test_unbacked_rating_is_cleared():
    [kept] = verify([book()], results("Meditations. A wonderful read."))
    assert (kept.rating, kept.rating_source, kept.rating_url) == (None, None, None)


def test_excerpt_normalization():
    [kept] = verify([book(review_excerpt='"a wonderful read"')],
                    results("Meditations. He said “a  wonderful read”…"))
    assert kept.review_excerpt == '"a wonderful read"'


def test_fabricated_excerpt_removed():
    [kept] = verify([book(review_excerpt="life changing masterpiece")])
    assert (kept.review_excerpt, kept.review_source_name, kept.review_url) == (None, None, None)


def test_long_excerpt_removed():
    long = "a wonderful read " * 30
    [kept] = verify([book(review_excerpt=long)], results("Meditations " + long))
    assert kept.review_excerpt is None


def test_duplicate_and_excluded_titles():
    books = [book(), book(title="meditations: a new translation"),
             book(title="Meditations (Penguin Classics)"), book(title="Letters")]
    kept = verify(books, results("Meditations Letters 4.3 a wonderful read"), exclude={"letters"})
    assert [b.title for b in kept] == ["Meditations"]


def test_max_pages_drops_unconfirmed_and_too_long():
    req = BookRequest(is_book_request=True, topic="stoicism", max_pages=200)
    res = [SearchResult(url=SRC, title="t", content="Meditations, 180 pages."),
           SearchResult(url="https://l", title="t", content="Letters, 350 pages."),
           SearchResult(url="https://e", title="t", content="Enchiridion by Epictetus.")]
    kept = verify([book(page_count=180),
                   book(title="Enchiridion", page_count=180, source_url="https://e"),
                   book(title="Letters", page_count=350, source_url="https://l")], res, request=req)
    assert [(b.title, b.page_count) for b in kept] == [("Meditations", 180)]


def test_unbacked_page_count_cleared_without_constraint():
    [kept] = verify([book(page_count=999)])
    assert kept.page_count is None


def test_year_constraint():
    req = BookRequest(is_book_request=True, topic="stoicism", min_year=2010)
    res = [SearchResult(url=SRC, title="t", content="Meditations published 2015. Letters published 2005.")]
    kept = verify([book(year=2015), book(title="Letters", year=2005)], res, request=req)
    assert [b.title for b in kept] == ["Meditations"]


def test_merges_already_and_caps_at_max_books():
    content = "A B C D E F G 4.3 a wonderful read"
    already = [book(title=t) for t in "ABCD"]
    new = [book(title=t) for t in "EFG"]
    kept = verify(new, results(content), max_books=5, already=already)
    assert [b.title for b in kept] == ["A", "B", "C", "D", "E"]
    assert len(verify(new, results(content), max_books=2)) == 2
