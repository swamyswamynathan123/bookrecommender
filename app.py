"""Book Finder — Streamlit chat UI."""

import logging
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage

from bookrec import wiring
from bookrec.config import ConfigError, MissingKeyError
from bookrec.graph import NODE_LABELS
from bookrec.render import CONFIG_ERROR_REPLY, ERROR_REPLY, LIMIT_REPLY, MISSING_KEYS_REPLY

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Book Finder", page_icon="📚")
st.title("📚 Book Finder")


@st.cache_resource
def get_app():
    return wiring.load()


try:
    graph, settings = get_app()
except MissingKeyError:
    st.error(MISSING_KEYS_REPLY)
    st.stop()
except ConfigError as e:
    st.error(CONFIG_ERROR_REPLY.format(details=str(e)))
    st.stop()

state = st.session_state
state.setdefault("thread_id", uuid.uuid4().hex)
state.setdefault("history", [])
state.setdefault("searches_used", 0)

with st.sidebar:
    if st.button("New search"):
        state.thread_id = uuid.uuid4().hex
        state.history = []
        st.rerun()
    left = max(settings.max_searches_per_session - state.searches_used, 0)
    st.caption(f"Searches left this session: {left}")

if not state.history:
    st.caption("Type a topic to get book recommendations — for example “Stoic philosophy”, "
               "“cozy mysteries” or “history of computing”. You can keep chatting to refine them.")

for item in state.history:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])


def answer(text: str) -> str:
    if state.searches_used >= settings.max_searches_per_session:
        return LIMIT_REPLY
    config = {"configurable": {"thread_id": state.thread_id}}
    try:
        with st.status("Working…", expanded=True) as status:
            for update in graph.stream({"messages": [HumanMessage(text)]}, config, stream_mode="updates"):
                for node in update:
                    if node in NODE_LABELS:
                        st.write(NODE_LABELS[node])
            status.update(label="Done", state="complete", expanded=False)
        values = graph.get_state(config).values
    except Exception:
        logger.exception("Recommendation run failed")
        return ERROR_REPLY
    if values.get("did_search"):
        state.searches_used += 1
    return values["reply"]


prompt = st.chat_input("Type a book topic…")
if prompt and prompt.strip():
    text = prompt.strip()[: settings.max_input_chars]
    state.history.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    with st.chat_message("assistant"):
        reply = answer(text)
        st.markdown(reply)
    state.history.append({"role": "assistant", "content": reply})
    st.rerun()
