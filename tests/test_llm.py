from bookrec.llm import format_results, select_prompt
from bookrec.models import BookRequest, SearchResult

RES = SearchResult(url="https://s", title="Best Stoic books", content="x" * 5000)


def test_format_results_truncates():
    block = format_results([RES])
    content = block.split("CONTENT: ", 1)[1]
    assert "URL: https://s" in block and len(content.strip()) <= 1500


def test_select_prompt_mentions_exclusions_and_rules():
    p = select_prompt(BookRequest(is_book_request=True, topic="stoicism", max_pages=200), [RES],
                      ["Meditations"], 5)
    assert "Meditations" in p and "verbatim" in p and "200" in p and "stoicism" in p
