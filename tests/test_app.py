from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from bookrec import wiring
from bookrec.config import ConfigError, MissingKeyError, Settings
from bookrec.graph import build_graph
from bookrec.models import Book, BookRequest, Candidate, SearchResult
from bookrec.render import ERROR_REPLY, LIMIT_REPLY, MISSING_KEYS_REPLY
from tests.fakes import FakeLLM, FakeSearch

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SRC = "https://src"


def fake_parts(raises=None):
    books = [Book(title=t, author="A", description="d", why_it_fits="w", source_url=SRC) for t in "ABCDE"]
    llm = FakeLLM(BookRequest(is_book_request=True, topic="stoicism"),
                  [Candidate(title=t, author="A") for t in "ABCDE"], [books] * 10)
    hit = [SearchResult(url=SRC, title="t", content="Stoic books: A, B, C, D, E.")]
    search = FakeSearch({"best books about": hit, "recommendations list": hit}, raises=raises)
    return llm, search


@pytest.fixture
def app(monkeypatch):
    def make(settings=None, raises=None, load_error=None):
        st.cache_resource.clear()
        settings = settings or Settings(openai_api_key="x", tavily_api_key="y")
        llm, search = fake_parts(raises)

        graph = build_graph(llm, search, settings)

        def load():
            if load_error:
                raise load_error
            return graph, settings

        monkeypatch.setattr(wiring, "load", load)
        at = AppTest.from_file(APP, default_timeout=30)
        at.run()
        at.graph = graph
        return at, llm, search

    yield make
    st.cache_resource.clear()


def chat_text(at) -> list[str]:
    return [" ".join(md.value for md in msg.markdown) for msg in at.chat_message]


def captions(at) -> str:
    return " ".join(c.value for c in at.sidebar.caption)


def test_topic_shows_books_and_counts_search(app):
    at, _, _ = app()
    at.chat_input[0].set_value("stoicism").run()
    assert any("Here are" in t for t in chat_text(at))
    assert "Searches left this session: 19" in captions(at)


def test_blank_and_long_input(app):
    at, llm, _ = app()
    at.chat_input[0].set_value("   ").run()
    assert chat_text(at) == [] and llm.parse_messages == []
    at.chat_input[0].set_value("x" * 5000).run()
    assert len(llm.parse_messages[-1]) == 500


def test_limit_blocks_search(app):
    at, _, search = app()
    at.session_state["searches_used"] = 20
    at.chat_input[0].set_value("stoicism").run()
    assert any(LIMIT_REPLY in t for t in chat_text(at)) and search.queries == []


def test_error_does_not_count(app):
    at, _, _ = app(raises=RuntimeError("tavily down"))
    at.chat_input[0].set_value("stoicism").run()
    assert any(ERROR_REPLY in t for t in chat_text(at))
    assert "Searches left this session: 20" in captions(at) and not at.exception


def test_missing_keys_message(app):
    at, _, _ = app(load_error=MissingKeyError("Missing required setting(s): OPENAI_API_KEY"))
    assert at.error[0].value == MISSING_KEYS_REPLY and not at.exception


def test_invalid_setting_message(app):
    at, _, _ = app(load_error=ConfigError("MAX_BOOKS must be a whole number >= 1"))
    assert "MAX_BOOKS" in at.error[0].value and not at.exception


def test_limits_come_from_settings(app):
    at, llm, _ = app(settings=Settings(openai_api_key="x", tavily_api_key="y",
                                       max_searches_per_session=2, max_input_chars=10))
    assert "Searches left this session: 2" in captions(at)
    at.chat_input[0].set_value("y" * 50).run()
    assert llm.parse_messages[-1] == "y" * 10


def test_new_search_clears_history(app):
    at, _, _ = app()
    at.chat_input[0].set_value("stoicism").run()
    assert chat_text(at)
    at.sidebar.button[0].click().run()
    assert chat_text(at) == []


def test_message_cap_includes_off_topic(app):
    at, llm, _ = app(settings=Settings(openai_api_key="x", tavily_api_key="y", max_messages_per_session=1))
    at.chat_input[0].set_value("stoicism").run()
    at.chat_input[0].set_value("what's the weather").run()
    assert len(llm.parse_messages) == 1 and any(LIMIT_REPLY in t for t in chat_text(at))


def test_new_search_deletes_old_thread(app):
    at, _, _ = app()
    at.chat_input[0].set_value("stoicism").run()
    old = at.session_state["thread_id"]
    assert at.graph.get_state({"configurable": {"thread_id": old}}).values
    at.sidebar.button[0].click().run()
    assert not at.graph.get_state({"configurable": {"thread_id": old}}).values
