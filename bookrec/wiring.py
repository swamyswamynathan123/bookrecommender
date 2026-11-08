"""Builds the real graph (OpenAI + Tavily) from settings."""

from bookrec.catalog import LookupFn, make_catalog_enricher, make_google_books_lookup, make_open_library_lookup
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
    enrich = make_catalog_enricher(catalog_lookups(settings), min_ratings=settings.min_catalog_ratings)
    graph = build_graph(llm, make_tavily_search(settings.tavily_api_key), settings, enrich=enrich)
    return graph, settings


def catalog_lookups(settings: Settings) -> list[LookupFn]:
    """Google Books first (only with a key: the keyless quota is shared and usually exhausted), then Open Library."""
    lookups: list[LookupFn] = []
    if settings.google_books_api_key:
        lookups.append(make_google_books_lookup(settings.google_books_api_key))
    lookups.append(make_open_library_lookup())
    return lookups
