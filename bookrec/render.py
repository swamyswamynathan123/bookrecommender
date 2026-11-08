"""User-facing copy and markdown for book cards and replies."""

from bookrec.models import Book

OFF_TOPIC_REPLY = "I can help you find books. Try a topic like “Stoic philosophy” or “cozy mysteries”."
NO_RESULTS_REPLY = "I couldn't find books I could confirm for that. Try a broader or different topic."
ERROR_REPLY = "Something went wrong while searching. Please try again in a moment."
LIMIT_REPLY = "You've reached the search limit for this session. Click “New search” in the sidebar or come back later."
MISSING_KEYS_REPLY = "The app isn't configured yet: API keys are missing. See the README."
CONFIG_ERROR_REPLY = "The app's settings are invalid: {details}. See the README."

_EXCERPT_STRIP = ' "“”'


def format_book_card(book: Book, index: int) -> str:
    meta = f"★ {book.rating:g} on {book.rating_source}" if book.rating is not None else "Rating not found"
    if book.page_count:
        meta += f" · {book.page_count} pages"
    if book.year:
        meta += f" · {book.year}"
    lines = [
        f"**{index}. {book.title}** — {book.author}",
        "",
        meta,
        "",
        book.description,
        "",
        f"*Why it fits:* {book.why_it_fits}",
    ]
    if book.review_excerpt:
        excerpt = book.review_excerpt.strip(_EXCERPT_STRIP)
        lines += ["", f"> “{excerpt}” — [{book.review_source_name}]({book.review_url})"]
    return "\n".join(lines)


def format_reply(books: list[Book], requested: int) -> str:
    n = len(books)
    intro = f"Here are {n} books for you:"
    if n < requested:
        intro += f"\n\n_I could only confirm {n} books for this request._"
    cards = [format_book_card(b, i) for i, b in enumerate(books, start=1)]
    return "\n\n---\n\n".join([intro, *cards])
