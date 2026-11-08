from langchain_core.messages import HumanMessage

from bookrec.config import Settings
from bookrec.graph import build_graph
from bookrec.models import Book, BookRequest, Candidate, SearchResult
from bookrec.render import NO_RESULTS_REPLY, OFF_TOPIC_REPLY
from tests.fakes import FakeLLM, FakeSearch

SRC = "https://src"
STOIC = BookRequest(is_book_request=True, topic="stoicism")
SETTINGS = Settings(openai_api_key="x", tavily_api_key="y")


def book(title: str) -> Book:
    return Book(title=title, author="Someone", description="d", why_it_fits="w", source_url=SRC)


def books(*titles: str) -> list[Book]:
    return [book(t) for t in titles]


def cands(n: int) -> list[Candidate]:
    return [Candidate(title=f"Book {i}", author="A") for i in range(n)]


def search_with_results() -> FakeSearch:
    hit = [SearchResult(url=SRC, title="Best Stoic books", content="Stoic books: A, B, C, D, E, F, Meditations.")]
    return FakeSearch({"best books about": hit, "recommendations list": hit})


def run(llm, search, settings=SETTINGS, thread="t1", text="stoicism", graph=None):
    graph = graph or build_graph(llm, search, settings)
    config = {"configurable": {"thread_id": thread}}
    graph.invoke({"messages": [HumanMessage(text)]}, config)
    return graph, graph.get_state(config).values


def test_happy_path_returns_five_books():
    search = search_with_results()
    _, state = run(FakeLLM(STOIC, cands(5), [books("A", "B", "C", "D", "E")]), search)
    assert state["reply"].startswith("Here are 5 books")
    assert state["did_search"] and state["tavily_calls"] <= 8 and len(search.queries) <= 8


def test_off_topic_skips_search():
    search = search_with_results()
    _, state = run(FakeLLM(BookRequest(is_book_request=False)), search, text="what's the weather")
    assert state["reply"] == OFF_TOPIC_REPLY and search.queries == [] and not state["did_search"]


def test_no_results_reply():
    _, state = run(FakeLLM(STOIC, cands(5), [books("A")]), FakeSearch({}))
    assert state["reply"] == NO_RESULTS_REPLY


def test_retry_once_when_short():
    search = search_with_results()
    _, state = run(FakeLLM(STOIC, cands(5), [books("A", "B"), books("C", "D", "E")]), search)
    assert state["reply"].startswith("Here are 5 books")
    assert sum("recommendations list" in q for q in search.queries) == 1


def test_budget_never_exceeds_eight():
    search = search_with_results()
    _, state = run(FakeLLM(STOIC, cands(10), [books("A"), books("B"), books("C")]), search)
    assert len(search.queries) <= 8
    assert sum("recommendations list" in q for q in search.queries) <= 1


def test_custom_limits_respected():
    search = search_with_results()
    settings = Settings(openai_api_key="x", tavily_api_key="y", max_books=3, max_tavily_calls_per_message=4)
    _, state = run(FakeLLM(STOIC, cands(5), [books("A", "B", "C", "D", "E")]), search, settings)
    assert state["reply"].startswith("Here are 3 books") and len(search.queries) <= 4


def test_followup_excludes_shown_books():
    llm = FakeLLM(STOIC, cands(5), [books("Meditations", "B", "C", "D", "E"),
                                    books("Meditations (Penguin Classics)", "F")])
    graph, _ = run(llm, search_with_results())
    _, state = run(llm, search_with_results(), graph=graph, text="more modern ones")
    assert "meditations" in llm.select_excludes[1]
    assert "**1. F**" in state["reply"] and "Meditations" not in state["reply"]


def test_new_thread_has_no_memory():
    llm = FakeLLM(STOIC, cands(5), [books("A", "B", "C", "D", "E"), books("F")])
    graph, _ = run(llm, search_with_results())
    run(llm, search_with_results(), graph=graph, thread="t2")
    assert llm.select_excludes[1] == []
