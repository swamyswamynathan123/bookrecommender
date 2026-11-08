# 📚 Book Finder

A chat app that recommends real books on any topic. Type a topic like "Stoic philosophy" or
"cozy mysteries" and you get about 5 books, each with a rating, a short description, why it fits,
and a review excerpt credited to the site it came from. Keep chatting to refine the results
("more modern", "under 200 pages", "more like the second one").

Built with Python, OpenAI, LangGraph, Tavily web search and Streamlit.

## What is fact-checked

Every book, rating, review excerpt, page count and publication year shown has to appear in the
Tavily search results. If it doesn't, it's dropped or shown as "Rating not found". The
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

The per-session search limit protects your API bill in a proof of concept. It resets when the
visitor reloads the page, so it isn't a hard cap.

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
