from bookrec import wiring


def test_load_configures_tracing(monkeypatch):
    calls = []
    monkeypatch.setattr(wiring, "get_settings", lambda: wiring.Settings(openai_api_key="x", tavily_api_key="y"))
    monkeypatch.setattr(wiring, "configure_tracing", lambda s: calls.append(s) or False)
    graph, settings = wiring.load()
    assert calls == [settings] and graph is not None
