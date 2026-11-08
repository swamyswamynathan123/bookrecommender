from langchain_core.messages import HumanMessage

from bookrec.config import Settings
from bookrec.graph import build_graph
from bookrec.models import BookRequest
from bookrec.threads import ThreadRegistry
from tests.fakes import FakeLLM, FakeSearch


def graph_with_threads(*ids):
    graph = build_graph(FakeLLM(BookRequest(is_book_request=False)), FakeSearch({}),
                        Settings(openai_api_key="x", tavily_api_key="y"))
    for tid in ids:
        graph.invoke({"messages": [HumanMessage("hi")]}, {"configurable": {"thread_id": tid}})
    return graph


def has_state(graph, tid) -> bool:
    return bool(graph.get_state({"configurable": {"thread_id": tid}}).values)


def test_registry_deletes_oldest_beyond_cap():
    graph = graph_with_threads("t1", "t2", "t3")
    reg = ThreadRegistry(graph.checkpointer, max_threads=2)
    for tid in ("t1", "t2", "t3"):
        reg.touch(tid)
    assert not has_state(graph, "t1") and has_state(graph, "t2") and has_state(graph, "t3")


def test_touch_keeps_recent_thread_alive():
    graph = graph_with_threads("t1", "t2", "t3")
    reg = ThreadRegistry(graph.checkpointer, max_threads=2)
    reg.touch("t1"); reg.touch("t2"); reg.touch("t1"); reg.touch("t3")
    assert has_state(graph, "t1") and not has_state(graph, "t2")


def test_forget_deletes_thread():
    graph = graph_with_threads("t1")
    reg = ThreadRegistry(graph.checkpointer, max_threads=5)
    reg.touch("t1"); reg.forget("t1")
    assert not has_state(graph, "t1")
