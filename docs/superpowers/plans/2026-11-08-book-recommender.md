# Book Recommender Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Streamlit chat app where a visitor types a book topic and gets ~5 real, source-backed book recommendations (rating, description, why it fits, credited review), and can keep chatting to refine them.

**Architecture:** A LangGraph `StateGraph` runs one turn per user message: understand → search_books → enrich → select_and_write → verify → (bounded retry) → respond. The LLM and the web search are injected behind small interfaces, so the whole graph is tested with fakes and no network. A pure `verify` module enforces grounding against Tavily results. The Streamlit `app.py` is a thin UI layer: chat, progress, usage limit, error messages.

**Tech Stack:** Python 3.11, LangGraph, langchain-openai (`ChatOpenAI.with_structured_output`), tavily-python, Streamlit, Pydantic v2, python-dotenv, pytest. Environment and installs via `uv` (installed: uv 0.9.16).

**Spec:** `docs/superpowers/specs/2026-11-08-book-recommender-design.md`

## Global Constraints

- Every book, rating, review excerpt, page count and publication year shown must be backed by Tavily result text. Unbacked rating → shown as "rating not found". Unbacked review → omitted. Unbacked page count / year → not shown. Book with no source → dropped.
- Description, "why it fits", and soft constraints ("more practical") may come from the LLM's own knowledge.
- Any credited review source is acceptable (reader sites, critics, blogs); the card names the source and links to it.
- ~5 books per answer (`max_books`, default 5).
- Usage cap: 20 user messages that ran a search per session (`max_searches_per_session`, default 20). Off-topic replies and runs that raise an error don't count.
- At most 8 Tavily calls per message (`max_tavily_calls_per_message`, default 8), including the retry.
- Input is cut to 500 characters (`max_input_chars`, default 500).
- **Every limit is configurable** with the same lookup as the keys (Streamlit secrets, then env / `.env`): `MAX_BOOKS`, `MAX_SEARCHES_PER_SESSION`, `MAX_TAVILY_CALLS_PER_MESSAGE`, `MAX_INPUT_CHARS`. A value that is set but isn't a whole number ≥ 1 is a configuration error that names the setting. It's never silently ignored. No code reads a hard-coded limit; everything goes through `Settings`.
- `start.bat` starts the app on Windows with one double-click.
- If fewer than 5 books pass verify: one extra search/enrich round within the budget, then show what survived with a note.
- Keys: `OPENAI_API_KEY`, `TAVILY_API_KEY`, optional `OPENAI_MODEL`, read from env / `.env` locally and from `st.secrets` on Streamlit Cloud. No key ever committed.
- `.gitignore` includes `.env`, `.streamlit/secrets.toml`, `.superpowers/`, `.venv/`, `__pycache__/`.
- No tracebacks shown to visitors.
- Out of scope: logins, saved lists, database, visitor 👍/👎, split-screen layout.

## Review Focus

1. **Rating written in different formats** ("4.30 avg rating", "4,3/5", "rated 4.3 out of 5"): a real 4.3 should be accepted, while "14.3" must not count as backing 4.3. Tested in Task 3 (`test_rating_formats`).
2. **Review excerpt differing from the source only in quotes, whitespace or an ellipsis** (`“great”` vs `"great"`): should still count as backed. Tested in Task 3 (`test_excerpt_normalization`).
3. **The same book under a slightly different title** ("Meditations" vs "Meditations (Penguin Classics)" vs "meditations: a new translation"), within one answer or across turns: should be treated as one book, so it's never repeated. Tested in Task 3 (`test_duplicate_and_excluded_titles`) and Task 5 (`test_followup_excludes_shown_books`).
4. **Blank or very long input** (only spaces; a 5,000-character paste): blank input is ignored, and long input is cut to 500 characters before it reaches the graph. Tested in Task 7 (`test_blank_and_long_input`).
5. **Tavily returning nothing, or raising mid-run:** nothing found → the "couldn't find" reply. An exception → a friendly error reply that doesn't count toward the cap. Tested in Task 5 (`test_no_results_reply`) and Task 7 (`test_error_does_not_count`).

---

## File Structure

```
bookrecommender/
  app.py                     # Streamlit UI (Task 7)
  bookrec/
    __init__.py
    config.py                # Settings + key loading (Task 1)
    models.py                # Pydantic models (Task 2)
    search.py                # Tavily adapter + budgeted queries (Task 2)
    verify.py                # Grounding checks, pure (Task 3)
    llm.py                   # BookLLM protocol + OpenAI implementation (Task 4)
    render.py                # Card/reply markdown + fixed copy (Task 4)
    graph.py                 # LangGraph workflow (Task 5)
    wiring.py                # Builds real graph from settings (Task 6)
  tests/
    fakes.py                 # FakeLLM, FakeSearch (Task 2, extended in 5)
    test_config.py  test_search.py  test_verify.py  test_llm.py
    test_render.py  test_graph.py  test_app.py
  requirements.txt  .gitignore  .env.example  README.md  start.bat  CLAUDE.md (Task 9)
  .streamlit/secrets.toml.example
```

---

### Task 1: Project scaffold and configuration

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `.streamlit/secrets.toml.example`, `bookrec/__init__.py`, `bookrec/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `class ConfigError(Exception)` and `class MissingKeyError(ConfigError)`. The message names the missing or invalid settings.
  - `@dataclass(frozen=True) class Settings: openai_api_key: str; tavily_api_key: str; openai_model: str = DEFAULT_MODEL; max_books: int = 5; max_searches_per_session: int = 20; max_tavily_calls_per_message: int = 8; max_input_chars: int = 500`
  - Env/secret names for the limits: `MAX_BOOKS`, `MAX_SEARCHES_PER_SESSION`, `MAX_TAVILY_CALLS_PER_MESSAGE`, `MAX_INPUT_CHARS`. Unset or empty means the default. A value that is set must parse as an int ≥ 1; otherwise raise `ConfigError` naming the setting. Surrounding whitespace is allowed.
  - `DEFAULT_MODEL = "gpt-4.1-mini"`. Before setting it, check OpenAI's models page for a current low-cost model that supports structured output, and use that name instead if this one is outdated.
  - `def get_settings(env: Mapping[str, str] | None = None, secrets: Mapping[str, str] | None = None) -> Settings`. Lookup order per key: `secrets`, then `env`. When `env` is None, it calls `load_dotenv()` and uses `os.environ`. When `secrets` is None, it tries `st.secrets` and treats any exception (no secrets file) as empty. Empty strings count as missing.

- [ ] **Step 1: Initialize the repo and environment**

Run: `git init` and `uv venv` (creates `.venv`).
Write `requirements.txt` with lower bounds: `langgraph>=1.0`, `langchain-openai>=0.3`, `langchain-core>=0.3`, `tavily-python>=0.5`, `streamlit>=1.40`, `pydantic>=2.7`, `python-dotenv>=1.0`, `pytest>=8`.
Run: `uv pip install -r requirements.txt`
Expected: installs without errors. Then pin the installed versions back into `requirements.txt` (`uv pip freeze`, keeping only the direct dependencies).
Write `.gitignore` (entries from Global Constraints), `.env.example`, and `.streamlit/secrets.toml.example` (the same settings in TOML form). `.env.example` contents:

```
OPENAI_API_KEY=
TAVILY_API_KEY=
# Optional settings (defaults shown)
OPENAI_MODEL=gpt-4.1-mini
MAX_BOOKS=5
MAX_SEARCHES_PER_SESSION=20
MAX_TAVILY_CALLS_PER_MESSAGE=8
MAX_INPUT_CHARS=500
```

- [ ] **Step 2: Write failing tests** in `tests/test_config.py`

```python
def test_reads_keys_from_env():
    s = get_settings(env={"OPENAI_API_KEY": "o", "TAVILY_API_KEY": "t"}, secrets={})
    assert (s.openai_api_key, s.tavily_api_key, s.openai_model) == ("o", "t", DEFAULT_MODEL)
    assert s.max_searches_per_session == 20 and s.max_tavily_calls_per_message == 8

def test_secrets_override_env_and_model_override():
    s = get_settings(env={"OPENAI_API_KEY": "o", "TAVILY_API_KEY": "t"},
                     secrets={"OPENAI_API_KEY": "o2", "OPENAI_MODEL": "m"})
    assert s.openai_api_key == "o2" and s.openai_model == "m"

def test_missing_keys_named_in_error():
    with pytest.raises(MissingKeyError, match="TAVILY_API_KEY"):
        get_settings(env={"OPENAI_API_KEY": "o", "TAVILY_API_KEY": ""}, secrets={})

KEYS = {"OPENAI_API_KEY": "o", "TAVILY_API_KEY": "t"}

def test_limits_from_env():
    s = get_settings(env={**KEYS, "MAX_BOOKS": " 3 ", "MAX_SEARCHES_PER_SESSION": "50",
                          "MAX_TAVILY_CALLS_PER_MESSAGE": "12", "MAX_INPUT_CHARS": "300"}, secrets={})
    assert (s.max_books, s.max_searches_per_session, s.max_tavily_calls_per_message, s.max_input_chars) == (3, 50, 12, 300)

def test_empty_limit_uses_default():
    assert get_settings(env={**KEYS, "MAX_BOOKS": ""}, secrets={}).max_books == 5

@pytest.mark.parametrize("bad", ["abc", "0", "-2", "2.5"])
def test_invalid_limit_names_setting(bad):
    with pytest.raises(ConfigError, match="MAX_SEARCHES_PER_SESSION"):
        get_settings(env={**KEYS, "MAX_SEARCHES_PER_SESSION": bad}, secrets={})
```

- [ ] **Step 3: Run** `.venv/Scripts/python -m pytest tests/test_config.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 4: Implement `bookrec/config.py`** per Interfaces.
- [ ] **Step 5: Run** the same command. Expected: all passed.
- [ ] **Step 6: Commit.** Run `git status` first and confirm no `.env` file is staged.

```bash
git add .gitignore requirements.txt .env.example .streamlit/secrets.toml.example bookrec tests
git commit -m "feat: project scaffold and settings loading"
```

---

### Task 2: Models and budgeted search

**Files:**
- Create: `bookrec/models.py`, `bookrec/search.py`, `tests/fakes.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces (`bookrec/models.py`, Pydantic `BaseModel`s):
  - `SearchResult(url: str, title: str, content: str)`
  - `BookRequest(is_book_request: bool, topic: str = "", soft_constraints: list[str] = [], like_title: str | None = None, max_pages: int | None = None, min_year: int | None = None, max_year: int | None = None)`
  - `Candidate(title: str, author: str)`
  - `Book(title: str, author: str, description: str, why_it_fits: str, source_url: str, rating: float | None = None, rating_source: str | None = None, rating_url: str | None = None, review_excerpt: str | None = None, review_source_name: str | None = None, review_url: str | None = None, page_count: int | None = None, year: int | None = None)`
- Produces (`bookrec/search.py`):
  - `SearchFn = Callable[[str, int], list[SearchResult]]` (query, max_results)
  - `def make_tavily_search(api_key: str) -> SearchFn`. Wraps `TavilyClient(api_key).search(query, max_results=..., search_depth="basic")` and maps each `results[]` item to `SearchResult`.
  - `def run_queries(search: SearchFn, queries: list[str], max_results: int, remaining: int) -> tuple[list[SearchResult], int]`. Runs queries in order until `remaining` is used up. Returns the results, de-duplicated by url (first one wins), and the number of calls made. Exceptions propagate.
- Produces (`tests/fakes.py`): `class FakeSearch`. `__init__(self, responses: dict[str, list[SearchResult]])` matches a response when its key is a substring of the query. It records `self.queries: list[str]`, and an unmatched query returns `[]`.

- [ ] **Step 1: Write failing tests** in `tests/test_search.py`

```python
def test_run_queries_respects_remaining_budget():
    fake = FakeSearch({"a": [r("u1")], "b": [r("u2")], "c": [r("u3")]})
    results, used = run_queries(fake, ["a", "b", "c"], max_results=3, remaining=2)
    assert used == 2 and fake.queries == ["a", "b"] and [x.url for x in results] == ["u1", "u2"]

def test_run_queries_dedupes_by_url():
    fake = FakeSearch({"a": [r("u1")], "b": [r("u1"), r("u2")]})
    results, used = run_queries(fake, ["a", "b"], 3, 8)
    assert used == 2 and [x.url for x in results] == ["u1", "u2"]

def test_zero_remaining_makes_no_calls():
    fake = FakeSearch({})
    assert run_queries(fake, ["a"], 3, 0) == ([], 0) and fake.queries == []
```
(`r(url)` is a local helper that builds a `SearchResult` with that url and dummy title and content.)

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_search.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `models.py`, `search.py` and `fakes.FakeSearch` per Interfaces. `make_tavily_search` gets no unit test; it's exercised in the Task 8 smoke test.
- [ ] **Step 4: Run** the same command. Expected: 3 passed.
- [ ] **Step 5: Commit** `git commit -am "feat: models and budgeted search"` (run `git add` on the new files first).

---

### Task 3: Grounding verification

**Files:**
- Create: `bookrec/verify.py`
- Test: `tests/test_verify.py`

**Interfaces:**
- Consumes: `Book`, `BookRequest`, `SearchResult` (Task 2)
- Produces:
  - `def normalize_text(s: str) -> str`: casefold, curly quotes → straight, remove `…` and `...`, collapse whitespace, strip.
  - `def normalize_title(title: str) -> str`: `normalize_text`, then cut at the first `:` or `(`, then strip.
  - `def rating_is_backed(rating: float, text: str) -> bool`: true if the number appears as a standalone number (no digit directly before it, so "14.3" doesn't match). Accept `.` or `,` as the decimal separator, and either the 1- or 2-decimal form (4.3 ↔ "4.30").
  - `def verify_books(books: list[Book], results: list[SearchResult], request: BookRequest, exclude_titles: set[str], max_books: int, already: list[Book] = []) -> list[Book]`

`verify_books` rules, applied in order (`url_map` = results by url):
1. Drop a book if `source_url` is not in `url_map`.
2. Drop it if `normalize_title(title)` is in `exclude_titles`, or matches a title in `already`, or matches one kept earlier in this call.
3. Rating: keep only if `rating_url` is in `url_map` and `rating_is_backed(rating, url_map[rating_url].content)`. Otherwise set `rating`, `rating_source` and `rating_url` to None.
4. Review: keep only if `review_url` is in `url_map`, `len(review_excerpt) <= 300`, and `normalize_text(excerpt)` is a substring of `normalize_text(content)`. Otherwise set all three review fields to None.
5. `page_count` / `year`: keep only if the number appears as a standalone number in a result whose normalized content contains `normalize_title(title)`. Otherwise set it to None.
6. Hard constraints: drop if `request.max_pages` is set and `page_count` is None or larger than it. Apply `min_year` / `max_year` against `year` the same way.
7. Return `already + kept`, truncated to `max_books`.

- [ ] **Step 1: Write failing tests** in `tests/test_verify.py`. Use a `book(**overrides)` helper whose defaults point every url at `"https://src"`, and a results list containing that url.

```python
def test_drops_book_without_known_source(): ...        # source_url "https://other" -> []
def test_rating_formats():
    assert rating_is_backed(4.3, "4.30 avg rating")
    assert rating_is_backed(4.3, "rated 4,3/5")
    assert rating_is_backed(4.35, "score 4.35 of 5")
    assert not rating_is_backed(4.3, "page 14.3")
    assert not rating_is_backed(4.3, "rated 4.4")
def test_unbacked_rating_is_cleared():                  # content lacks rating -> rating/rating_source/rating_url None, book kept
def test_excerpt_normalization():                       # content 'He said “a  wonderful read”…' backs excerpt '"a wonderful read"'
def test_fabricated_excerpt_removed():                  # excerpt not in content -> review fields None
def test_duplicate_and_excluded_titles():
    # books "Meditations", "meditations: a new translation", "Meditations (Penguin Classics)", "Letters"
    # exclude_titles={"letters"} -> exactly one book kept, titled "Meditations"
def test_max_pages_drops_unconfirmed_and_too_long():
    # max_pages=200: page_count 180 backed -> kept; 180 not in any text -> dropped; 350 backed -> dropped
def test_year_constraint():                             # min_year=2010: year 2015 backed kept, 2005 dropped
def test_merges_already_and_caps_at_max_books():        # max_books=5: already has 4, 3 new valid -> 5 returned, already first; max_books=2 -> 2
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_verify.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement `bookrec/verify.py`** per the rules above.
- [ ] **Step 4: Run** the same command. Expected: all passed.
- [ ] **Step 5: Commit** `"feat: grounding verification"`.

---

### Task 4: LLM adapter and rendering

**Files:**
- Create: `bookrec/llm.py`, `bookrec/render.py`
- Test: `tests/test_llm.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: models (Task 2)
- Produces (`bookrec/llm.py`):
  - `class BookLLM(Protocol)`:
    - `parse_request(self, history: list[BaseMessage], message: str) -> BookRequest`
    - `extract_candidates(self, request: BookRequest, results: list[SearchResult], exclude_titles: list[str], limit: int) -> list[Candidate]`
    - `select_books(self, request: BookRequest, results: list[SearchResult], exclude_titles: list[str], count: int) -> list[Book]`
  - `def format_results(results: list[SearchResult], max_chars_each: int = 1500) -> str`: numbered blocks of `URL: …\nTITLE: …\nCONTENT: …`, with content truncated.
  - `def select_prompt(request, results, exclude_titles, count) -> str`. The prompt must say:
    - choose only books named in the results;
    - set `source_url`, `rating_url` and `review_url` to URLs from the results;
    - copy the review excerpt verbatim (≤ 300 characters);
    - leave rating, page count and year empty unless they're stated in the results;
    - never choose any title in `exclude_titles`;
    - honour the soft constraints and `like_title`.
  - `class OpenAIBookLLM(BookLLM)`. `__init__(self, model: str, api_key: str)` creates `ChatOpenAI(model=model, api_key=api_key, temperature=0)`. Each method calls `.with_structured_output(...)` with a wrapper model (`class BookList(BaseModel): books: list[Book]`, and `CandidateList` the same way). `parse_request` gets a system prompt saying it should:
    - set `is_book_request=False` for messages that aren't about finding books;
    - resolve references like "the second one" from the history;
    - carry the previous topic forward on refinements.
- Produces (`tests/fakes.py`): `class FakeLLM(BookLLM)`, constructed with `request: BookRequest`, `candidates: list[Candidate]`, and `books: list[list[Book]]` (one list per `select_books` call, consumed in order). It records the `exclude_titles` passed to each call in `self.select_excludes`.
- Produces (`bookrec/render.py`), exact copy:
  - `OFF_TOPIC_REPLY = "I can help you find books. Try a topic like “Stoic philosophy” or “cozy mysteries”."`
  - `NO_RESULTS_REPLY = "I couldn't find books I could confirm for that. Try a broader or different topic."`
  - `ERROR_REPLY = "Something went wrong while searching. Please try again in a moment."`
  - `LIMIT_REPLY = "You've reached the search limit for this session. Click “New search” in the sidebar or come back later."`
  - `MISSING_KEYS_REPLY = "The app isn't configured yet: API keys are missing. See the README."`
  - `def format_book_card(book: Book, index: int) -> str`: markdown with
    - `**{index}. {title}** — {author}`;
    - `★ {rating} on {rating_source}`, or `Rating not found`;
    - ` · {page_count} pages` / ` · {year}` when present;
    - the description;
    - `*Why it fits:* …`;
    - the review as `> “excerpt” — [{review_source_name}]({review_url})`, but only when present.
  - `CONFIG_ERROR_REPLY = "The app's settings are invalid: {details}. See the README."` (format it with the `ConfigError` message)
  - `def format_reply(books: list[Book], requested: int) -> str` (the graph passes `settings.max_books`). The intro is `"Here are {n} books for you:"`. If `n < requested`, append `"\n\n_I could only confirm {n} books for this request._"`. Cards are separated by blank lines.

- [ ] **Step 1: Write failing tests**

`tests/test_render.py`:
```python
def test_card_with_all_fields():   # contains "★ 4.3 on Goodreads", "180 pages", "> “Great read” — [Kirkus](https://k)"
def test_card_without_rating_or_review():  # contains "Rating not found", no ">" line
def test_reply_notes_short_list(): # 3 books -> "Here are 3 books for you:" and "I could only confirm 3 books"
```
`tests/test_llm.py`:
```python
def test_format_results_truncates():   # 5000-char content -> block content length <= 1500
def test_select_prompt_mentions_exclusions_and_rules():
    p = select_prompt(BookRequest(is_book_request=True, topic="stoicism", max_pages=200), [res], ["Meditations"], 5)
    assert "Meditations" in p and "verbatim" in p and "200" in p
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_render.py tests/test_llm.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `render.py`, `llm.py` and `FakeLLM` per Interfaces.
- [ ] **Step 4: Run** the same command. Expected: all passed.
- [ ] **Step 5: Commit** `"feat: LLM adapter and reply rendering"`.

---

### Task 5: LangGraph workflow

**Files:**
- Create: `bookrec/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `BookLLM`, `SearchFn`, `run_queries`, `verify_books`, `normalize_title`, `format_reply`, `OFF_TOPIC_REPLY`, `NO_RESULTS_REPLY`, `Settings`
- Produces:
  - `class TurnState(TypedDict)` with these fields:
    - `messages: Annotated[list, add_messages]`
    - `shown_titles: Annotated[list[str], operator.add]` (normalized, persists across turns)
    - Per-turn fields, reset by `understand`: `request: BookRequest | None`, `results: list[SearchResult]`, `books: list[Book]`, `tavily_calls: int`, `attempts: int`, `reply: str`, `did_search: bool`
  - `NODE_LABELS: dict[str, str]`:
    - `understand` → "Understanding your request…"
    - `search_books` → "Searching the web…"
    - `enrich` → "Reading reviews…"
    - `select_and_write` → "Picking the best matches…"
    - `verify` → "Checking the facts…"
  - `def build_graph(llm: BookLLM, search: SearchFn, settings: Settings, checkpointer=None) -> CompiledStateGraph`. The default checkpointer is `MemorySaver()`. Callers invoke with `{"messages": [HumanMessage(text)]}` and `config={"configurable": {"thread_id": tid}}`.

Node behaviour:
- **understand:** calls `llm.parse_request(history_without_last, last_text)` and resets the per-turn fields. If `not is_book_request`, it routes to respond.
- **search_books:** query template by attempt:
  - attempt 0: `f"best books about {topic}"`, plus the hard constraints in words ("under N pages", "published after Y");
  - attempt 1: `f"{topic} book recommendations list"`.

  It makes 1 call with `max_results=8`, through `run_queries` against the remaining budget (`settings.max_tavily_calls_per_message - tavily_calls`), appends the results, and sets `did_search=True`.
In the nodes below, `N = settings.max_books`, and the budget is `settings.max_tavily_calls_per_message`.
- **enrich:** `limit = min(N - len(books), remaining)`. It calls `llm.extract_candidates(...)` (excluding `shown_titles` and the titles of current books), then runs one query per candidate with `max_results=3`: `f'"{title}" {author} book rating review'`, adding `" pages"` if `max_pages` is set and `" published"` if a year bound is set.
- **select_and_write:** calls `llm.select_books(request, results, exclude, N - len(books))`.
- **verify:** calls `verify_books(new, results, request, set(shown_titles), max_books=N, already=books)`. It routes back to search_books (attempts+1) when `len(books) < N and attempts == 0 and remaining >= 2`; otherwise it routes to respond.
- **respond:** sets the reply:
  - off-topic → `OFF_TOPIC_REPLY`;
  - no books → `NO_RESULTS_REPLY`;
  - otherwise `format_reply(books, N)`.

  It appends `AIMessage(reply)` and adds the books' normalized titles to `shown_titles`.

- [ ] **Step 1: Write failing tests** in `tests/test_graph.py`, using `FakeLLM` and `FakeSearch` with `Settings(openai_api_key="x", tavily_api_key="y")`:

```python
def test_happy_path_returns_five_books():      # 5 valid books -> reply starts "Here are 5 books", tavily_calls <= 8, did_search
def test_off_topic_skips_search():             # is_book_request False -> reply == OFF_TOPIC_REPLY, FakeSearch.queries == [], did_search False
def test_no_results_reply():                    # search returns [] everywhere -> reply == NO_RESULTS_REPLY
def test_retry_once_when_short():               # first select gives 2 valid, second gives 3 -> 5 books, exactly one "recommendations list" query
def test_budget_never_exceeds_eight():          # candidates list of 10, books short both rounds -> len(fake.queries) <= 8
def test_custom_limits_respected():             # Settings(max_books=3, max_tavily_calls_per_message=4) -> <= 3 books, len(fake.queries) <= 4, reply "Here are 3 books"
def test_followup_excludes_shown_books():
    # same thread_id, two invokes; 2nd FakeLLM select call's exclude list contains normalized titles from turn 1,
    # and a returned "Meditations (Penguin Classics)" duplicate of a turn-1 book is dropped by verify
def test_new_thread_has_no_memory():            # different thread_id -> select_excludes empty
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_graph.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `bookrec/graph.py`** per Interfaces and node behaviour.
- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -v`. Expected: the whole suite passes.
- [ ] **Step 5: Commit** `"feat: LangGraph recommendation workflow"`.

---

### Task 6: Wiring

**Files:**
- Create: `bookrec/wiring.py`

**Interfaces:**
- Consumes: `get_settings`, `OpenAIBookLLM`, `make_tavily_search`, `build_graph`
- Produces: `def load() -> tuple[CompiledStateGraph, Settings]`. It raises `MissingKeyError` if keys are missing. The app caches it with `st.cache_resource`, so `wiring.py` itself does not import Streamlit for caching.

- [ ] **Step 1: Implement `load()`.**
- [ ] **Step 2: Verify:** `.venv/Scripts/python -c "import bookrec.wiring"` exits 0.
- [ ] **Step 3: Commit** `"feat: wire real LLM and search"`.

---

### Task 7: Streamlit app

**Files:**
- Create: `app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `wiring.load`, `NODE_LABELS`, `render.*_REPLY`, `ConfigError`, `MissingKeyError`, `Settings.max_input_chars`, `Settings.max_searches_per_session`

Behaviour:
- `st.set_page_config(page_title="Book Finder", page_icon="📚")` and the title "📚 Book Finder". When the chat is empty, show a welcome caption with example topics.
- Get the graph through `@st.cache_resource def get_app(): return wiring.load()`. On `MissingKeyError`, show `st.error(MISSING_KEYS_REPLY)`. On any other `ConfigError`, show `st.error(CONFIG_ERROR_REPLY.format(details=str(e)))`. In both cases, then `st.stop()`.
- `st.session_state` holds `thread_id` (uuid4 hex), `history` (a list of `{"role", "content"}` dicts to replay), and `searches_used` (int).
- The sidebar has a "New search" button, which gives a new `thread_id`, clears `history` and calls `st.rerun()` (it doesn't reset `searches_used`), and the caption `"Searches left this session: {n}"`.
- On `st.chat_input("Type a book topic…")`:
  1. Strip the text; if it's empty, do nothing.
  2. Truncate it to `settings.max_input_chars`.
  3. If `searches_used >= settings.max_searches_per_session`, reply with `LIMIT_REPLY`.
  4. Otherwise, inside `st.status("Working…")`, iterate over `graph.stream(..., stream_mode="updates")` and write `NODE_LABELS[node]` for each update.
  5. Read the reply from `graph.get_state(config).values["reply"]`. If `did_search` is set, increment `searches_used`.
  6. Catch any exception: log it with `logging.exception`, reply with `ERROR_REPLY`, and don't increment the counter.
  7. Append both messages to `history` and render them with `st.chat_message`.

- [ ] **Step 1: Write failing tests** in `tests/test_app.py` with `streamlit.testing.v1.AppTest.from_file("app.py")`. `monkeypatch` `bookrec.wiring.load` to return `(build_graph(FakeLLM…, FakeSearch…, Settings(...)), settings)`, and clear the `st.cache_resource` cache between tests.

```python
def test_topic_shows_books_and_counts_search():  # input "stoicism" -> a chat message contains "Here are"; sidebar shows "Searches left this session: 19"
def test_blank_and_long_input():                  # "   " -> no new messages; 5000-char input -> FakeLLM received message of len 500
def test_limit_blocks_search():                   # set session_state.searches_used = 20 -> LIMIT_REPLY shown, FakeSearch.queries == []
def test_error_does_not_count():                  # FakeSearch raises RuntimeError -> ERROR_REPLY shown, counter still 20 left
def test_missing_keys_message():                  # load raises MissingKeyError -> st.error with MISSING_KEYS_REPLY, no exception element
def test_invalid_setting_message():               # load raises ConfigError("MAX_BOOKS must be a whole number >= 1") -> st.error contains "MAX_BOOKS"
def test_limits_come_from_settings():             # Settings(max_searches_per_session=2, max_input_chars=10) -> sidebar "Searches left this session: 2"; long input cut to 10 chars
def test_new_search_clears_history():             # click sidebar button -> no chat messages rendered
```
`FakeLLM.parse_request` records the message it received; extend it in `tests/fakes.py` if it doesn't already. `FakeSearch` accepts `raises: Exception | None`.

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_app.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `app.py`** per Behaviour.
- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -v`. Expected: all passed.
- [ ] **Step 5: Commit** `"feat: Streamlit chat UI"`.

---

### Task 8: start.bat, README and live smoke test

**Files:**
- Create: `start.bat`, `README.md`

- [ ] **Step 1: Write `start.bat`** (Windows, run from any folder). It should:
  1. `cd /d "%~dp0"` so it works on double-click.
  2. If `uv` isn't on PATH, print an install hint and `pause`.
  3. If `.venv` doesn't exist, run `uv venv` and `uv pip install -r requirements.txt`.
  4. If `.env` doesn't exist, copy `.env.example` to `.env`, print "Fill in your API keys in .env, then run start.bat again.", then `pause` and exit.
  5. Run `.venv\Scripts\streamlit run app.py`.
  6. If Streamlit exits with an error, `pause` so the window stays open and the error stays readable.
- [ ] **Step 2: Verify `start.bat`:**
  - Rename `.env` away, run `start.bat`: it creates `.env` from the example and stops with the message.
  - Restore `.env`, run it again: the browser opens the app at `http://localhost:8501`.
- [ ] **Step 3: Write `README.md`.** It covers:
  - what the app does;
  - setup: `uv venv`, `uv pip install -r requirements.txt`, copy `.env.example` to `.env` and fill in the keys;
  - running it: double-click `start.bat`, or `.venv/Scripts/streamlit run app.py`;
  - a table of every setting in `.env` (name, default, meaning), noting that the same names go into Streamlit Cloud's Secrets;
  - running the tests;
  - deploying to Streamlit Community Cloud: push to GitHub, create the app pointing at `app.py`, and paste the keys into **Settings → Secrets** in TOML format, as in `.streamlit/secrets.toml.example`;
  - the search limit and what is and isn't fact-checked.
- [ ] **Step 4: Live smoke test** (needs the owner's `.env` with real keys). Run `.venv/Scripts/streamlit run app.py`, then try:
  - "Stoic philosophy" → about 5 cards; each rating either names a source or says "Rating not found"; review links open real pages;
  - "something more modern" → no repeated books;
  - "under 200 pages" → cards show page counts ≤ 200, or fewer books with the note;
  - "what's the weather" → the off-topic reply.

  Record any failures as issues before continuing.
- [ ] **Step 5: Run** `git status`. Confirm `.env` is untracked and ignored (`git check-ignore .env` prints `.env`).
- [ ] **Step 6: Commit** `start.bat` and `README.md` with the message `"docs: start.bat and README with setup and deployment"`.

---

### Task 9: CLAUDE.md

Done last, after Tasks 1–8 pass, so it describes the code as actually built rather than as planned.

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`** from the finished code. Keep it short (well under 100 lines) and only include what a future Claude session can't quickly read off the code. Cover:
  - **Commands:**
    - run the app with `start.bat` or `.venv/Scripts/streamlit run app.py`;
    - run all tests with `.venv/Scripts/python -m pytest -v`, or a single test with `-k`;
    - add a dependency with `uv pip install …`, then pin it in `requirements.txt`.
  - **Architecture map:** one line per module in `bookrec/` plus `app.py`. Include the graph's node order and the single bounded retry.
  - **Rules not to break:**
    - Everything shown as fact (book, rating, review, page count, year) must pass `verify.py`. Never relax that to "make results look fuller".
    - Description, "why it fits" and soft constraints may come from the LLM.
    - Every limit goes through `Settings` in `config.py`. Never hard-code one. A new limit also gets added to `.env.example`, `.streamlit/secrets.toml.example`, and the README settings table.
    - Tests never call OpenAI or Tavily; they use `tests/fakes.py`. Real APIs are used only for the manual smoke test.
    - Never commit `.env` or `secrets.toml`, and never print key values.
    - Visitors never see tracebacks; user-facing copy lives in `render.py`.
  - **Pointers:** links to the spec (`docs/superpowers/specs/2026-11-08-book-recommender-design.md`) and this plan.
- [ ] **Step 2: Verify** that every command in `CLAUDE.md` runs as written, and that every file and function it names exists (Grep for each).
- [ ] **Step 3: Commit** `"docs: add CLAUDE.md"`. Pushing to GitHub is the owner's step; don't push without their go-ahead.
