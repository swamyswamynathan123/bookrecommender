# CLAUDE.md

Book Finder: a Streamlit chat app that recommends real books on a topic, using OpenAI (via
LangChain), LangGraph and Tavily web search. Proof of concept: runs locally, later on Streamlit
Community Cloud.

## Commands

- Run the app: `start.bat` (Windows), or `.venv/Scripts/streamlit run app.py`
- All tests: `.venv/Scripts/python -m pytest -v`. One test: `.venv/Scripts/python -m pytest -k <name>`
- Add a dependency: `uv pip install <pkg>`, then pin it with `==` in `requirements.txt`

## Architecture

- `app.py`: Streamlit UI. Chat history, progress labels, per-session search counter, friendly errors.
- `bookrec/config.py`: `Settings` and `get_settings()`. Keys and limits come from Streamlit secrets first, then env / `.env`.
- `bookrec/graph.py`: the LangGraph workflow. One invocation per user message; memory per thread via `MemorySaver`.
  The nodes run understand → search_books → enrich → select_and_write → verify, then respond.
  When verify keeps fewer than `max_books` books, it may retry once (via `retry`, back to search_books) if 2 or more Tavily calls are left.
  An off-topic message goes from understand straight to respond.
- `bookrec/verify.py`: grounding checks against Tavily result text (pure functions). Facts must appear near the book's title in a result.
- `bookrec/catalog.py`: Open Library / Google Books lookups and `enrich_from_catalogs` (fills gaps on verified books; title+author must match). Runs inside `verify_books`, after grounding and before hard constraints.
- `bookrec/llm.py`: the `BookLLM` protocol, prompts, and `OpenAIBookLLM` (structured output).
- `bookrec/search.py`: the Tavily adapter and `run_queries` (enforces the per-message call budget).
- `bookrec/render.py`: all user-facing copy and the book-card markdown.
- `bookrec/models.py`: Pydantic models shared by everything above.
- `bookrec/wiring.py`: `load()` builds the real graph from settings and calls `configure_tracing`.
- `bookrec/telemetry.py`: exports LangSmith settings to env vars (needed when they come from Streamlit secrets).
- `bookrec/threads.py`: `ThreadRegistry` deletes old conversations from the shared in-memory checkpointer.

## Rules not to break

- Everything shown as fact (book, rating, review excerpt, page count, year) must pass `verify.py`.
  Never relax verification to "make results look fuller". Source names shown come from URL domains, not LLM text. Description, "why it fits" and soft
  preferences may come from the LLM.
- Every limit lives in `Settings` (`config.py`). Never hard-code one. A new setting also goes into
  `.env.example`, `.streamlit/secrets.toml.example` and the README settings table.
- Tests never call OpenAI or Tavily; use `tests/fakes.py` (`FakeLLM`, `FakeSearch`). Real APIs are
  only for manual smoke tests with a filled-in `.env`.
- Never commit `.env` or `.streamlit/secrets.toml`, and never print key values.
- New Pydantic types stored in graph state must be added to `CHECKPOINT_TYPES` in `graph.py`.
- Catalog-only Book fields (`cover_url`, `ratings_count`, `google_books_url`, `open_library_url`) are cleared in `verify.py` and set only by `catalog.py`, never from the LLM.
- Keys never go in URLs (Google Books key is sent as the `X-Goog-Api-Key` header) so they can't leak into logs or traces.
- Tracing is optional: everything must work with `LANGSMITH_TRACING` off and no LangSmith key.
- Visitors never see tracebacks. User-facing text lives in `render.py`.
- The OpenAI SDK sends Pydantic models as strict JSON schemas. Keep model fields simple
  (str, int, float, bool, lists, Optional) so that conversion keeps working.

## Docs

- Design: `docs/superpowers/specs/2026-11-08-book-recommender-design.md`
- Plan: `docs/superpowers/plans/2026-11-08-book-recommender.md`
