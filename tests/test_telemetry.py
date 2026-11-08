from bookrec.config import Settings
from bookrec.telemetry import configure_tracing


def settings(**kw) -> Settings:
    return Settings(openai_api_key="x", tavily_api_key="y", **kw)


def test_tracing_on_exports_langsmith_env():
    env = {}
    assert configure_tracing(settings(langsmith_tracing=True, langsmith_api_key="ls",
                                      langsmith_project="p", langsmith_endpoint="https://eu"), env)
    assert env == {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "ls",
                   "LANGSMITH_PROJECT": "p", "LANGSMITH_ENDPOINT": "https://eu"}


def test_tracing_on_without_endpoint_leaves_default():
    env = {}
    configure_tracing(settings(langsmith_tracing=True, langsmith_api_key="ls"), env)
    assert "LANGSMITH_ENDPOINT" not in env and env["LANGSMITH_PROJECT"] == "book-finder"


def test_tracing_off_disables_even_if_env_had_it():
    env = {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true"}
    assert not configure_tracing(settings(), env)
    assert env["LANGSMITH_TRACING"] == "false" and env["LANGCHAIN_TRACING_V2"] == "false"
