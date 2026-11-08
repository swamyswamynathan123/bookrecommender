from bookrec.models import Book, BookRequest, SearchResult
from bookrec.verify import normalize_title, rating_is_backed, verify_books

SRC = "https://www.goodreads.com/book/1"
REQ = BookRequest(is_book_request=True, topic="stoicism")
EXCERPT = "a wonderful read for any student of Stoicism"


def book(**overrides) -> Book:
    fields = dict(
        title="Meditations", author="Marcus Aurelius", description="d", why_it_fits="w",
        source_url=SRC, rating=4.3, rating_source="Goodreads", rating_url=SRC,
        review_excerpt=EXCERPT, review_source_name="Goodreads", review_url=SRC,
    )
    fields.update(overrides)
    return Book(**fields)


def results(content=f"Meditations by Marcus Aurelius. 4.30 avg rating. {EXCERPT}.", url=SRC) -> list[SearchResult]:
    return [SearchResult(url=url, title="t", content=content)]


def verify(books, res=None, request=REQ, exclude=frozenset(), max_books=5, already=None):
    return verify_books(books, res if res is not None else results(), request, set(exclude),
                        max_books=max_books, already=already or [])


def test_drops_book_without_known_source():
    assert verify([book(source_url="https://other")]) == []


def test_drops_invented_book_with_valid_url():
    assert verify([book(title="Totally Invented Book")]) == []


def test_rating_formats():
    assert rating_is_backed(4.3, "4.30 avg rating")
    assert rating_is_backed(4.3, "rated 4,3/5")
    assert rating_is_backed(4.3, "rated 4.3 out of 5")
    assert rating_is_backed(4.35, "score 4.35 of 5")
    assert not rating_is_backed(4.3, "page 14.3")
    assert not rating_is_backed(4.3, "rated 4.4")


def test_rating_false_positives_rejected():
    assert not rating_is_backed(4.0, "4.5 avg rating")
    assert not rating_is_backed(4.0, "Top 4 books")
    assert rating_is_backed(4.0, "4 stars")
    assert rating_is_backed(4.0, "rated 4.00 out of 5")
    assert not rating_is_backed(4.3, "costs $4.30")
    assert not rating_is_backed(4.3, "4.3 million copies sold")
    assert not rating_is_backed(4.3, "version v4.3")
    assert not rating_is_backed(4.3, "scored 4.3/10")


def test_rating_from_other_book_on_list_page_cleared():
    far = " filler" * 60
    content = f"Dune by Frank Herbert.{far} Meditations by Marcus Aurelius is wonderful, 4.3 avg rating."
    kept = verify([book(title="Dune", author="Frank Herbert")], results(content))
    assert kept and kept[0].rating is None


def test_unbacked_rating_is_cleared():
    [kept] = verify([book()], results(f"Meditations. {EXCERPT}"))
    assert (kept.rating, kept.rating_source, kept.rating_url) == (None, None, None)


def test_source_names_come_from_urls():
    [kept] = verify([book(rating_source="Kirkus", review_source_name="NYT")])
    assert kept.rating_source == "goodreads.com" and kept.review_source_name == "goodreads.com"


def test_excerpt_normalization():
    [kept] = verify([book(review_excerpt=f'"{EXCERPT}"')],
                    results(f"Meditations. He said “a  wonderful read for any student of Stoicism”…"))
    assert kept.review_excerpt == f'"{EXCERPT}"'


def test_fabricated_excerpt_removed():
    [kept] = verify([book(review_excerpt="a life changing masterpiece of ancient wisdom")])
    assert (kept.review_excerpt, kept.review_source_name, kept.review_url) == (None, None, None)


def test_trivial_and_partial_word_excerpts_removed():
    content = f"Meditations by Marcus Aurelius. 4.3 avg rating. {EXCERPT}. Truly a great read."
    for excerpt in ["a", "eat rea", "a wonderful read", "onderful read for any student of Stoic"]:
        [kept] = verify([book(review_excerpt=excerpt)], results(content))
        assert kept.review_excerpt is None, excerpt


def test_negated_excerpt_removed():
    content = "Meditations by Marcus Aurelius. Honestly this is not a great read for anyone at all."
    [kept] = verify([book(review_excerpt="a great read for anyone at all")], results(content))
    assert kept.review_excerpt is None


def test_review_source_must_mention_book():
    res = results() + [SearchResult(url="https://blog", title="t", content=f"Dune review: {EXCERPT}")]
    [kept] = verify([book(review_url="https://blog")], res)
    assert kept.review_excerpt is None


def test_long_excerpt_removed():
    long = "a wonderful read " * 30
    [kept] = verify([book(review_excerpt=long)], results("Meditations " + long))
    assert kept.review_excerpt is None


def test_title_variants_normalize_together():
    variants = ["Meditations", "The Meditations", "Meditations - A New Translation",
                "Meditations — Gregory Hays", "Meditations by Marcus Aurelius",
                "Meditations (Penguin Classics)", "meditations: a new translation"]
    assert {normalize_title(v) for v in variants} == {"meditations"}


def test_duplicate_and_excluded_titles():
    books = [book(), book(title="meditations: a new translation"),
             book(title="The Meditations"), book(title="Letters")]
    kept = verify(books, results(f"Meditations Letters 4.3 avg rating {EXCERPT}"), exclude={"letters"})
    assert [b.title for b in kept] == ["Meditations"]


def test_max_pages_drops_unconfirmed_and_too_long():
    req = BookRequest(is_book_request=True, topic="stoicism", max_pages=200)
    res = [SearchResult(url=SRC, title="t", content="Meditations, 180 pages."),
           SearchResult(url="https://l", title="t", content="Letters, 350 pages."),
           SearchResult(url="https://e", title="t", content="Enchiridion by Epictetus. 180 reviews.")]
    kept = verify([book(page_count=180),
                   book(title="Enchiridion", page_count=180, source_url="https://e"),
                   book(title="Letters", page_count=350, source_url="https://l")], res, request=req)
    assert [(b.title, b.page_count) for b in kept] == [("Meditations", 180)]


def test_page_count_from_other_book_not_accepted():
    far = " filler" * 60
    res = results(f"Dune by Frank Herbert.{far} Meditations, 180 pages.")
    [kept] = verify([book(title="Dune", page_count=180)], res)
    assert kept.page_count is None


def test_unbacked_page_count_cleared_without_constraint():
    [kept] = verify([book(page_count=999)])
    assert kept.page_count is None


def test_year_constraint():
    req = BookRequest(is_book_request=True, topic="stoicism", min_year=2010)
    res = [SearchResult(url=SRC, title="t", content="Meditations published 2015."),
           SearchResult(url="https://l", title="t", content="Letters published 2005.")]
    kept = verify([book(year=2015), book(title="Letters", year=2005, source_url="https://l")], res, request=req)
    assert [b.title for b in kept] == ["Meditations"]


def test_merges_already_and_caps_at_max_books():
    content = "Alpha Bravo Charlie Delta Echo Foxtrot Golf"
    names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf"]
    already = [book(title=t) for t in names[:4]]
    new = [book(title=t) for t in names[4:]]
    kept = verify(new, results(content), max_books=5, already=already)
    assert [b.title for b in kept] == names[:5]
    assert len(verify(new, results(content), max_books=2)) == 2
