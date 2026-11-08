"""User-facing copy and markdown for book cards and replies."""

from bookrec.models import Book

OFF_TOPIC_REPLY = "I can help you find books. Try a topic like “Stoic philosophy” or “cozy mysteries”."
NO_RESULTS_REPLY = "I couldn't find books I could confirm for that. Try a broader or different topic."
ERROR_REPLY = "Something went wrong while searching. Please try again in a moment."
LIMIT_REPLY = "You've reached the search limit for this session. Please come back later."
MISSING_KEYS_REPLY = "The app isn't configured yet: API keys are missing. See the README."
CONFIG_ERROR_REPLY = "The app's settings are invalid: {details}. See the README."

_EXCERPT_STRIP = ' "“”'


def format_book_card(book: Book, index: int) -> str:
    if book.rating is not None:
        meta = f"★ {book.rating:g} on [{book.rating_source}]({book.rating_url})"
        if book.ratings_count:
            meta += f" · {book.ratings_count:,} ratings"
    else:
        meta = "Rating not found"
    if book.page_count:
        meta += f" · {book.page_count} pages"
    if book.year:
        meta += f" · {book.year}"
    lines = [f"![Cover of {book.title}]({book.cover_url})", ""] if book.cover_url else []
    lines += [
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
    links = []
    if book.google_books_url:
        links.append(f"[Preview on Google Books]({book.google_books_url})")
    if book.open_library_url:
        links.append(f"[View on Open Library]({book.open_library_url})")
    if links:
        lines += ["", " · ".join(links)]
    return "\n".join(lines)


def format_reply(books: list[Book], requested: int) -> str:
    n = len(books)
    intro = f"Here are {n} books for you:"
    if n < requested:
        intro += f"\n\n_I could only confirm {n} books for this request._"
    cards = [format_book_card(b, i) for i, b in enumerate(books, start=1)]
    return "\n\n---\n\n".join([intro, *cards])
