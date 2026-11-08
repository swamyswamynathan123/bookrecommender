# 📚 Book Finder

A chat app that recommends real books on any topic. Type a topic like "Stoic philosophy" or
"cozy mysteries" and you get about 5 books, each with a rating, a short description, why it fits,
and a review excerpt credited to the site it came from. Keep chatting to refine the results
("more modern", "under 200 pages", "more like the second one").

Built with Python, OpenAI, LangGraph, Tavily web search and Streamlit, with book data from Open Library
(and optionally Google Books) and optional LangSmith tracing.

How it works inside, as built: [docs/DESIGN.md](docs/DESIGN.md).

## What is fact-checked

Every book, rating, review excerpt, page count and publication year shown has to appear in the
Tavily search results, next to that book's title (so a list page can't lend one book's rating to
another). If it doesn't, it's dropped or shown as "Rating not found". Ratings and reviews link to
the page they came from.

After the web check, each book is looked up in Open Library (and Google Books if you add a key).
A catalog record only counts if its title and author match. Catalogs add a cover, links, the page
count and the rating when the web search didn't find them (labeled with the source and number of
ratings), and the earliest publication year. Catalog ratings come from those sites' own, smaller
reader communities, so a web-found Goodreads rating is always preferred. The
description and the "why it fits" line are written by the AI and are not fact-checked.
Reviews may come from readers (Goodreads, Amazon, Reddit) or critics (Kirkus, blogs); each one
names and links its source.

## Setup (Windows)

1. Install [uv](https://docs.astral.sh/uv/).
2. Double-click `start.bat`. The first time, it creates the Python environment, installs the
   dependencies and creates `.env` from `.env.example`.
3. Open `.env` and fill in `OPENAI_API_KEY` and `TAVILY_API_KEY`.
4. Double-click `start.bat` again. The app opens at http://localhost:8501.

Manual alternative:

```
uv venv
uv pip install -r requirements.txt
copy .env.example .env      (then fill in the keys)
.venv\Scripts\streamlit run app.py
```

## Settings

All settings go in `.env` locally, or in **Settings → Secrets** on Streamlit Community Cloud,
with the same names. Leave an optional setting blank to use its default. A limit that isn't a
whole number of at least 1 stops the app with a message naming it.

| Setting | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | (required) | Your OpenAI key |
| `TAVILY_API_KEY` | (required) | Your Tavily key |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model; must support structured output |
| `MAX_BOOKS` | 5 | Books per answer |
| `MAX_SEARCHES_PER_SESSION` | 20 | Searches each visitor gets per browser session (off-topic messages and errors don't count) |
| `MAX_TAVILY_CALLS_PER_MESSAGE` | 8 | Tavily calls per message, including one retry when too few books check out |
| `MAX_INPUT_CHARS` | 500 | Longer messages are cut to this length |
| `MAX_MESSAGES_PER_SESSION` | 60 | All messages per session, including off-topic ones (caps OpenAI spend) |
| `MAX_CONVERSATIONS` | 200 | Conversations kept in server memory; the oldest are forgotten beyond this |
| `MIN_CATALOG_RATINGS` | 10 | A Google Books / Open Library rating is shown only if at least this many people rated the book |
| `GOOGLE_BOOKS_API_KEY` | (optional) | Adds Google Books data. Get a free key: Google Cloud Console → enable "Books API" → Credentials → API key. Without it, only Open Library is used |
| `LANGSMITH_TRACING` | false | `true` sends a trace of every message to LangSmith |
| `LANGSMITH_API_KEY` | (required if tracing) | Your LangSmith key |
| `LANGSMITH_PROJECT` | `book-finder` | LangSmith project the traces go to |
| `LANGSMITH_ENDPOINT` | (LangSmith default) | Only for non-default regions, e.g. `https://eu.api.smith.langchain.com` |

The per-session limits protect your API bill in a proof of concept. They reset when the
visitor reloads the page, so they aren't a hard cap.

## Telemetry (LangSmith)

With `LANGSMITH_TRACING=true`, each visitor message becomes one trace (`book_finder_turn`) in your
LangSmith project. A trace shows every step (understand, search, read reviews, pick, check, and
the retry if one happens), each OpenAI call with its prompt, tokens and timing, and each Tavily
query (`tavily_search`) with its results. Traces from one conversation share a `session_id`, so
LangSmith groups them into a thread.

**Privacy:** everything visitors type, and the search results, is stored in your LangSmith account.
Mention this to people before sharing a public link.

## Tests

```
.venv\Scripts\python -m pytest -v
```

The tests use fake OpenAI and Tavily stand-ins (`tests/fakes.py`), so they cost nothing and need no keys.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub. `.env` and `.streamlit/secrets.toml` are git-ignored and never pushed.
2. On [share.streamlit.io](https://share.streamlit.io), create an app from the repo with main file `app.py`.
3. In the app's **Settings → Secrets**, paste your settings in TOML form (see
   `.streamlit/secrets.toml.example`), for example:

   ```toml
   OPENAI_API_KEY = "sk-..."
   TAVILY_API_KEY = "tvly-..."
   ```
