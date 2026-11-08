"""LangSmith tracing setup.

LangChain/LangGraph read LangSmith settings from environment variables. Settings may come from
Streamlit secrets (not the environment), so we export them explicitly before any LLM call.
"""

import os
from collections.abc import MutableMapping

from bookrec.config import Settings


def configure_tracing(settings: Settings, environ: MutableMapping[str, str] = os.environ) -> bool:
    """Turn LangSmith tracing on or off from settings. Returns True if tracing is on."""
    if not settings.langsmith_tracing:
        environ["LANGSMITH_TRACING"] = "false"
        environ["LANGCHAIN_TRACING_V2"] = "false"
        return False
    environ["LANGSMITH_TRACING"] = "true"
    environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    return True
