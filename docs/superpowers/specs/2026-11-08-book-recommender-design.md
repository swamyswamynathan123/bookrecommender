# Book Recommender — Design

Date: 2026-11-08
Status: Draft, awaiting owner approval

## Intent

A public, chat-style web app where anyone can type a topic ("Stoic philosophy",
"cozy mysteries", "history of computing") and get back a short list of **real**
books that fit, each with a description, a rating, and real reader review
excerpts. The visitor can keep chatting to refine the results.

It is a proof of concept: built and tested locally first, pushed to the owner's
GitHub, and later deployed to Streamlit Community Cloud. The owner's own OpenAI
and Tavily accounts pay for usage.

## Goals

- Turn a free-text topic into ~5 relevant, real book recommendations.
- For each book show: title, author, rating (with its source), a 2–3 sentence
  description, one line on why it fits the request, and a short review excerpt
  credited to the site it came from, with a link.
- Support follow-up refinement in the same conversation ("more modern",
  "under 200 pages", "more like the second one") without repeating books
  already shown.
- Run locally with keys from `.env`; move to Streamlit Community Cloud later
  with no code changes.

## Non-goals (for this proof of concept)

- User accounts, logins, saved reading lists.
- A database or any persistence beyond the current browser session.
- Visitor 👍/👎 feedback on recommendations.
- The split-screen layout (considered, rejected in favour of pure chat).

## Anti-goals (failure even if it "works")

1. **Invented books, ratings, or reviews.** Every book, rating and review shown
   must trace back to Tavily search results. If a rating can't be found, show
   "rating not found" — never a guessed number. Review excerpts must be text
   that actually appeared in a result, credited to its site.
2. **Off-topic picks** (generic bestsellers for a specific topic).
3. **Forgetting the conversation** — restarting or repeating books on a
   follow-up.
4. **Looking frozen** while searching; the user must see progress.
5. **Crashing with a stack trace** on a missing key, API error, or empty result.
6. **API keys committed to GitHub.**

## Decided by the owner

- Python, OpenAI LLM, LangGraph for the workflow, Tavily for web search,
  Streamlit for the UI.
- Input is a topic name in a chat box.
- Output includes description, rating, and reviews (excerpts found on the
  web — reader or critic, always credited — not visitor feedback).
- Grounding strictness and acceptable review sources as described under
  Guardrails.
- Conversation continues for refinement.
- Pure chat layout (book cards appear inside the conversation).
- Guardrails as listed below.
- Keys kept in `.env` (local), hidden from code and from Git.
- Local first → GitHub → Streamlit Community Cloud later.

## Design

### User experience

- Single Streamlit page, title like "📚 Book Finder", using Streamlit's chat
  components (`st.chat_message` / `st.chat_input`).
- Welcome line with a few example topics.
- While working, show progress steps, e.g. "Searching the web…",
  "Reading reviews…", "Picking the best matches…" (e.g. `st.status`).
- Each answer: one short intro line, then ~5 book cards. Card fields:
  - Title — Author
  - ★ rating + source (e.g. "4.3 on Goodreads") or "rating not found"
  - Description (2–3 sentences)
  - "Why it fits:" one line
  - Review excerpt in quotes, "— site name", link to the source page
    (omitted if no review was found)
- Sidebar: "New search" button that clears the conversation; remaining
  searches for this session.

### Workflow (LangGraph)

One graph invocation per user message. Suggested nodes:

1. **understand** — LLM turns the message + conversation history into a
   structured request: topic, constraints (era, length, level, "like X"),
   and whether it is a new search or a refinement.
2. **search_books** — Tavily searches for candidate books on the topic and
   constraints.
3. **enrich** — for the best candidates, Tavily searches for rating and
   reader reviews (e.g. Goodreads / Amazon / similar pages).
4. **select_and_write** — LLM picks ~5 books using only the search results,
   excluding books already shown, and returns structured output (title,
   author, rating, rating_source, description, why_it_fits, review_excerpt,
   review_source_name, review_url).
5. **verify** — code-level check against the retrieved text: drop or downgrade
   anything not backed by a source (rating not present → "rating not found";
   review text not present → omit review). Drop books with no source at all.
6. **respond** — format the cards for the UI.

Graph state carries the messages, the parsed request, search results, and the
list of books already shown. The verify → search_books retry loop is bounded
(see Guardrails). Conversation memory per visitor uses a LangGraph
checkpointer keyed by a per-Streamlit-session thread id (in-memory is fine for
the PoC).

### Guardrails

- **Grounding** — enforced by the verify step above (anti-goal 1). Owner
  decision on how strict:
  - **Must be backed by search results:** the book itself, rating, review
    excerpt, and any number or date shown or used to satisfy a constraint
    (page count, publication year). If a constraint like "under 200 pages" or
    "after 2010" can't be confirmed from results, the book is dropped. So
    enrich must also look for page count / publication year when the request
    has such a constraint.
  - **May come from the LLM's own knowledge:** the description and the
    "why it fits" line, and soft constraints like "more practical" or
    "beginner-friendly".
- **Reviews** — owner decision: any credited review is acceptable (reader
  sites like Goodreads/Amazon/Reddit, critics like Kirkus or Publishers
  Weekly, or book blogs). The card labels the source name and links to it.
  The excerpt must be text that appeared in a search result.
- **Usage limit** — per-visitor-session cap of 20 *user messages that run a
  search* (designer's call). Off-topic replies and runs that fail with an
  error don't count. Each message also has a fixed Tavily budget (designer's
  call: at most ~8 Tavily calls per message, covering search, enrich and any
  retry), so spend per session stays bounded. A session-level counter is
  acceptable for the PoC, knowing it resets on reload.
- **Too few results** — if fewer than 5 books pass verify, do one extra
  search/enrich round within the per-message budget, then show however many
  survived with a short note (designer's call).
- **Errors** — missing keys, Tavily/OpenAI failures, and "nothing found"
  each produce a friendly message in the chat, never a traceback.
- **Off-topic input** — if the message isn't about finding books, reply
  politely and steer back, without running a search.

### Configuration & secrets

- Read `OPENAI_API_KEY`, `TAVILY_API_KEY` (and optional `OPENAI_MODEL`) from
  environment / `.env` locally, and from `st.secrets` when on Streamlit Cloud.
- `.env` and `.streamlit/secrets.toml` and `.superpowers/` in `.gitignore`;
  provide `.env.example` with placeholder values.
- README: setup, run locally, deploy to Streamlit Community Cloud.

## Left to the builder

- Exact OpenAI model (make it configurable; default to a current low-cost
  model that supports structured output).
- Exact Tavily queries, number of results, and how many candidates to enrich
  (balance quality against latency and cost).
- Project layout, dependency management, and test approach (graph logic
  should be testable without real API calls).
- Exact card styling within Streamlit.
- Whether to stream the final text or show it all at once.
