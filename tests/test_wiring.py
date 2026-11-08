from bookrec import wiring


def test_load_configures_tracing(monkeypatch):
    calls = []
    monkeypatch.setattr(wiring, "get_settings", lambda: wiring.Settings(openai_api_key="x", tavily_api_key="y"))
    monkeypatch.setattr(wiring, "configure_tracing", lambda s: calls.append(s) or False)
    graph, settings = wiring.load()
    assert calls == [settings] and graph is not None


def test_catalog_lookups_include_google_only_with_key(monkeypatch):
    monkeypatch.setattr(wiring, "make_open_library_lookup", lambda: "ol")
    monkeypatch.setattr(wiring, "make_google_books_lookup", lambda key: f"gb:{key}")
    base = wiring.Settings(openai_api_key="x", tavily_api_key="y")
    assert wiring.catalog_lookups(base) == ["ol"]
    with_key = wiring.Settings(openai_api_key="x", tavily_api_key="y", google_books_api_key="k")
    assert wiring.catalog_lookups(with_key) == ["gb:k", "ol"]
