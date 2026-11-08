"""LangGraph workflow: one invocation per visitor message."""

import operator
from collections.abc import Callable
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from bookrec.config import Settings
from bookrec.llm import BookLLM
from bookrec.models import Book, BookRequest, SearchResult
from bookrec.render import NO_RESULTS_REPLY, OFF_TOPIC_REPLY, format_reply
from bookrec.search import SearchFn, run_queries
from bookrec.verify import normalize_title, verify_books

NODE_LABELS = {
    "understand": "Understanding your request…",
    "search_books": "Searching the web…",
    "enrich": "Reading reviews…",
    "select_and_write": "Picking the best matches…",
    "verify": "Checking the facts…",
}

SEARCH_RESULTS_PER_QUERY = 8
ENRICH_RESULTS_PER_QUERY = 3
# Only the most recent messages (truncated) go to the request parser, to bound OpenAI cost.
HISTORY_MESSAGES = 6
HISTORY_MESSAGE_CHARS = 2000
# Our Pydantic models stored in checkpoints, registered so LangGraph deserializes them explicitly.
CHECKPOINT_TYPES = [("bookrec.models", name) for name in ("BookRequest", "SearchResult", "Book", "Candidate")]


class TurnState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    shown_titles: Annotated[list[str], operator.add]
    request: BookRequest | None
    results: list[SearchResult]
    candidates_new: list[Book]
    books: list[Book]
    tavily_calls: int
    attempts: int
    reply: str
    did_search: bool


def _constraint_words(request: BookRequest) -> str:
    words = []
    if request.max_pages:
        words.append(f"under {request.max_pages} pages")
    if request.min_year:
        words.append(f"published after {request.min_year}")
    if request.max_year:
        words.append(f"published before {request.max_year}")
    return (" " + " ".join(words)) if words else ""


def build_graph(llm: BookLLM, search: SearchFn, settings: Settings, checkpointer=None,
                enrich: Callable[[list[Book]], list[Book]] | None = None):
    catalog_enrich = enrich  # the 'enrich' node below shadows this name
    budget = settings.max_tavily_calls_per_message
    n_books = settings.max_books

    def remaining(state: TurnState) -> int:
        return budget - state.get("tavily_calls", 0)

    def excluded(state: TurnState) -> list[str]:
        titles = list(state.get("shown_titles", []))
        titles += [normalize_title(b.title) for b in state.get("books", [])]
        return list(dict.fromkeys(titles))

    def understand(state: TurnState) -> TurnState:
        *history, last = state["messages"]
        recent = [m.model_copy(update={"content": str(m.content)[:HISTORY_MESSAGE_CHARS]})
                  for m in history[-HISTORY_MESSAGES:]]
        request = llm.parse_request(recent, last.content)
        return {"request": request, "results": [], "candidates_new": [], "books": [],
                "tavily_calls": 0, "attempts": 0, "reply": "", "did_search": False}

    def search_books(state: TurnState) -> TurnState:
        request = state["request"]
        if state.get("attempts", 0) == 0:
            query = f"best books about {request.topic}{_constraint_words(request)}"
        else:
            query = f"{request.topic} book recommendations list"
        found, used = run_queries(search, [query], SEARCH_RESULTS_PER_QUERY, remaining(state))
        return {"results": _merge(state.get("results", []), found),
                "tavily_calls": state.get("tavily_calls", 0) + used, "did_search": True}

    def enrich(state: TurnState) -> TurnState:
        request = state["request"]
        limit = min(n_books - len(state.get("books", [])), remaining(state))
        if limit <= 0 or not state.get("results"):
            return {}
        candidates = llm.extract_candidates(request, state["results"], excluded(state), limit)
        suffix = (" pages" if request.max_pages else "") + (
            " published" if request.min_year or request.max_year else "")
        queries = [f'"{c.title}" {c.author} book rating review{suffix}' for c in candidates[:limit]]
        found, used = run_queries(search, queries, ENRICH_RESULTS_PER_QUERY, remaining(state))
        return {"results": _merge(state["results"], found),
                "tavily_calls": state.get("tavily_calls", 0) + used}

    def select_and_write(state: TurnState) -> TurnState:
        if not state.get("results"):
            return {"candidates_new": []}
        count = n_books - len(state.get("books", []))
        return {"candidates_new": llm.select_books(state["request"], state["results"],
                                                   excluded(state), count)}

    def verify(state: TurnState) -> TurnState:
        kept = verify_books(state.get("candidates_new", []), state.get("results", []), state["request"],
                            set(state.get("shown_titles", [])), max_books=n_books,
                            already=state.get("books", []), enrich=catalog_enrich)
        return {"books": kept, "candidates_new": []}

    def after_verify(state: TurnState) -> str:
        if len(state["books"]) < n_books and state.get("attempts", 0) == 0 and remaining(state) >= 2:
            return "retry"
        return "respond"

    def retry(state: TurnState) -> TurnState:
        return {"attempts": state.get("attempts", 0) + 1}

    def respond(state: TurnState) -> TurnState:
        request = state.get("request")
        found = state.get("books", [])
        if request is None or not request.is_book_request:
            reply = OFF_TOPIC_REPLY
        elif not found:
            reply = NO_RESULTS_REPLY
        else:
            reply = format_reply(found, n_books)
        return {"reply": reply, "messages": [AIMessage(reply)],
                "shown_titles": [normalize_title(b.title) for b in found]}

    graph = StateGraph(TurnState)
    for name, fn in [("understand", understand), ("search_books", search_books), ("enrich", enrich),
                     ("select_and_write", select_and_write), ("verify", verify), ("retry", retry),
                     ("respond", respond)]:
        graph.add_node(name, fn)
    graph.add_edge(START, "understand")
    graph.add_conditional_edges(
        "understand", lambda s: "search_books" if s["request"].is_book_request else "respond",
        ["search_books", "respond"])
    graph.add_edge("search_books", "enrich")
    graph.add_edge("enrich", "select_and_write")
    graph.add_edge("select_and_write", "verify")
    graph.add_conditional_edges("verify", after_verify, {"retry": "retry", "respond": "respond"})
    graph.add_edge("retry", "search_books")
    graph.add_edge("respond", END)
    if checkpointer is None:
        checkpointer = MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES))
    return graph.compile(checkpointer=checkpointer)


def _merge(existing: list[SearchResult], new: list[SearchResult]) -> list[SearchResult]:
    seen = {r.url for r in existing}
    return list(existing) + [r for r in new if r.url not in seen and not seen.add(r.url)]
