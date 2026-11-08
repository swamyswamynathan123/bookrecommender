"""Tavily adapter and budgeted query runner."""

from collections.abc import Callable

from bookrec.models import SearchResult

SearchFn = Callable[[str, int], list[SearchResult]]


def make_tavily_search(api_key: str) -> SearchFn:
    from langsmith import traceable
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)

    # Shows each Tavily query and its results inside the LangSmith trace (no-op when tracing is off)
    @traceable(run_type="tool", name="tavily_search")
    def search(query: str, max_results: int) -> list[SearchResult]:
        response = client.search(query, max_results=max_results, search_depth="basic")
        return [
            SearchResult(url=item.get("url", ""), title=item.get("title", ""),
                         content=item.get("content", ""))
            for item in response.get("results", [])
            if item.get("url")
        ]

    return search


def run_queries(
    search: SearchFn, queries: list[str], max_results: int, remaining: int
) -> tuple[list[SearchResult], int]:
    """Run queries in order until the budget is used; dedupe results by url."""
    results: list[SearchResult] = []
    seen: set[str] = set()
    used = 0
    for query in queries:
        if used >= remaining:
            break
        used += 1
        for result in search(query, max_results):
            if result.url not in seen:
                seen.add(result.url)
                results.append(result)
    return results, used
