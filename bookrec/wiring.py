"""Builds the real graph (OpenAI + Tavily) from settings."""

from bookrec.config import Settings, get_settings
from bookrec.graph import build_graph
from bookrec.llm import OpenAIBookLLM
from bookrec.search import make_tavily_search
from bookrec.telemetry import configure_tracing


def load() -> tuple:
    """Return (compiled graph, settings). Raises ConfigError / MissingKeyError."""
    settings: Settings = get_settings()
    configure_tracing(settings)
    llm = OpenAIBookLLM(model=settings.openai_model, api_key=settings.openai_api_key)
    graph = build_graph(llm, make_tavily_search(settings.tavily_api_key), settings)
    return graph, settings
