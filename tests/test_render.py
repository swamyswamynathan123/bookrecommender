from bookrec.models import Book
from bookrec.render import format_book_card, format_reply


def book(**kw) -> Book:
    base = dict(title="Meditations", author="Marcus Aurelius", description="Notes to himself.",
                why_it_fits="Core Stoic text.", source_url="https://s")
    base.update(kw)
    return Book(**base)


def test_card_with_all_fields():
    card = format_book_card(book(rating=4.3, rating_source="Goodreads", rating_url="https://g",
                                 page_count=180, year=2002, review_excerpt="Great read",
                                 review_source_name="Kirkus", review_url="https://k"), 1)
    assert "**1. Meditations** — Marcus Aurelius" in card
    assert "★ 4.3 on [Goodreads](https://g)" in card and "180 pages" in card and "2002" in card
    assert "*Why it fits:* Core Stoic text." in card
    assert "> “Great read” — [Kirkus](https://k)" in card


def test_card_without_rating_or_review():
    card = format_book_card(book(), 2)
    assert "Rating not found" in card and ">" not in card


def test_limit_reply_does_not_promise_new_search_resets():
    from bookrec.render import LIMIT_REPLY
    assert "New search" not in LIMIT_REPLY


def test_reply_notes_short_list():
    reply = format_reply([book(title=t) for t in "ABC"], 5)
    assert reply.startswith("Here are 3 books for you:")
    assert "I could only confirm 3 books" in reply


def test_reply_full_list_has_no_note():
    assert "could only" not in format_reply([book(title=t) for t in "ABCDE"], 5)


def test_card_with_catalog_data():
    card = format_book_card(book(rating=4.8, rating_source="Open Library", rating_url="https://ol",
                                 ratings_count=6, cover_url="https://cover.jpg",
                                 google_books_url="https://gb", open_library_url="https://ol"), 1)
    assert "![Cover of Meditations](https://cover.jpg)" in card
    assert "★ 4.8 on [Open Library](https://ol) · 6 ratings" in card
    assert "[Preview on Google Books](https://gb) · [View on Open Library](https://ol)" in card
