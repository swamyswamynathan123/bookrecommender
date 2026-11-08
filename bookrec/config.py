"""Settings loading: API keys and limits from Streamlit secrets or env / .env."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_LANGSMITH_PROJECT = "book-finder"

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}

# Env/secret name -> (Settings field, default)
_LIMITS = {
    "MAX_BOOKS": ("max_books", 5),
    "MAX_SEARCHES_PER_SESSION": ("max_searches_per_session", 20),
    "MAX_TAVILY_CALLS_PER_MESSAGE": ("max_tavily_calls_per_message", 8),
    "MAX_INPUT_CHARS": ("max_input_chars", 500),
    "MAX_MESSAGES_PER_SESSION": ("max_messages_per_session", 60),
    "MAX_CONVERSATIONS": ("max_conversations", 200),
    "MIN_CATALOG_RATINGS": ("min_catalog_ratings", 10),
}


class ConfigError(Exception):
    """A setting is missing or invalid. The message names the setting(s)."""


class MissingKeyError(ConfigError):
    """One or more required API keys are missing."""


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    tavily_api_key: str
    openai_model: str = DEFAULT_MODEL
    max_books: int = 5
    max_searches_per_session: int = 20
    max_tavily_calls_per_message: int = 8
    max_input_chars: int = 500
    max_messages_per_session: int = 60
    max_conversations: int = 200
    min_catalog_ratings: int = 10
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = DEFAULT_LANGSMITH_PROJECT
    langsmith_endpoint: str = ""
    google_books_api_key: str = ""


def _streamlit_secrets() -> Mapping[str, str]:
    try:
        import streamlit as st

        return {k: v for k, v in st.secrets.items() if isinstance(v, (str, int))}
    except Exception:
        return {}


def get_settings(
    env: Mapping[str, str] | None = None,
    secrets: Mapping[str, str] | None = None,
) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ
    if secrets is None:
        secrets = _streamlit_secrets()

    def lookup(name: str) -> str:
        for source in (secrets, env):
            value = str(source.get(name, "") or "").strip()
            if value:
                return value
        return ""

    missing = [k for k in ("OPENAI_API_KEY", "TAVILY_API_KEY") if not lookup(k)]
    if missing:
        raise MissingKeyError(f"Missing required setting(s): {', '.join(missing)}")

    limits: dict[str, int] = {}
    for name, (field, default) in _LIMITS.items():
        raw = lookup(name)
        if not raw:
            limits[field] = default
            continue
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value < 1:
            raise ConfigError(f"{name} must be a whole number >= 1 (got {raw!r})")
        limits[field] = value

    raw_tracing = lookup("LANGSMITH_TRACING").lower()
    if raw_tracing and raw_tracing not in _TRUE | _FALSE:
        raise ConfigError(f"LANGSMITH_TRACING must be true or false (got {raw_tracing!r})")
    tracing = raw_tracing in _TRUE
    if tracing and not lookup("LANGSMITH_API_KEY"):
        raise ConfigError("LANGSMITH_TRACING is true but LANGSMITH_API_KEY is missing")

    return Settings(
        openai_api_key=lookup("OPENAI_API_KEY"),
        tavily_api_key=lookup("TAVILY_API_KEY"),
        openai_model=lookup("OPENAI_MODEL") or DEFAULT_MODEL,
        langsmith_tracing=tracing,
        langsmith_api_key=lookup("LANGSMITH_API_KEY"),
        langsmith_project=lookup("LANGSMITH_PROJECT") or DEFAULT_LANGSMITH_PROJECT,
        langsmith_endpoint=lookup("LANGSMITH_ENDPOINT"),
        google_books_api_key=lookup("GOOGLE_BOOKS_API_KEY"),
        **limits,
    )
