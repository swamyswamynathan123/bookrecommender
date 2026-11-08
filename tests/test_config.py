import pytest

from bookrec.config import DEFAULT_MODEL, ConfigError, MissingKeyError, get_settings

KEYS = {"OPENAI_API_KEY": "o", "TAVILY_API_KEY": "t"}


def test_reads_keys_from_env():
    s = get_settings(env=KEYS, secrets={})
    assert (s.openai_api_key, s.tavily_api_key, s.openai_model) == ("o", "t", DEFAULT_MODEL)
    assert s.max_searches_per_session == 20 and s.max_tavily_calls_per_message == 8
    assert s.max_books == 5 and s.max_input_chars == 500


def test_secrets_override_env_and_model_override():
    s = get_settings(env=KEYS, secrets={"OPENAI_API_KEY": "o2", "OPENAI_MODEL": "m"})
    assert s.openai_api_key == "o2" and s.openai_model == "m"


def test_missing_keys_named_in_error():
    with pytest.raises(MissingKeyError, match="TAVILY_API_KEY"):
        get_settings(env={"OPENAI_API_KEY": "o", "TAVILY_API_KEY": ""}, secrets={})


def test_limits_from_env():
    s = get_settings(
        env={**KEYS, "MAX_BOOKS": " 3 ", "MAX_SEARCHES_PER_SESSION": "50",
             "MAX_TAVILY_CALLS_PER_MESSAGE": "12", "MAX_INPUT_CHARS": "300"},
        secrets={},
    )
    assert (s.max_books, s.max_searches_per_session,
            s.max_tavily_calls_per_message, s.max_input_chars) == (3, 50, 12, 300)


def test_empty_limit_uses_default():
    assert get_settings(env={**KEYS, "MAX_BOOKS": ""}, secrets={}).max_books == 5


@pytest.mark.parametrize("bad", ["abc", "0", "-2", "2.5"])
def test_invalid_limit_names_setting(bad):
    with pytest.raises(ConfigError, match="MAX_SEARCHES_PER_SESSION"):
        get_settings(env={**KEYS, "MAX_SEARCHES_PER_SESSION": bad}, secrets={})


def test_message_and_conversation_limits():
    s = get_settings(env={**KEYS, "MAX_MESSAGES_PER_SESSION": "7", "MAX_CONVERSATIONS": "9"}, secrets={})
    assert (s.max_messages_per_session, s.max_conversations) == (7, 9)
    d = get_settings(env=KEYS, secrets={})
    assert (d.max_messages_per_session, d.max_conversations) == (60, 200)
