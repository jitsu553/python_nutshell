from functools import lru_cache
import httpx
from dataclasses import dataclass
from typing import Protocol

from app.llm_chat.config import get_llm_settings
from bs4 import BeautifulSoup


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchEngine(Protocol):
    """Anything with this shape can be plugged in as a web search backend."""

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        ...

class DuckDuckGoSearchEngine:
    """Concrete SearchEngine strategy — scrapes DuckDuckGo's no-JS HTML results page."""

    _URL = "https://html.duckduckgo.com/html/"
    _HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; fast_api-llm-chat-agent/1.0)"}

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(headers=self._HEADERS, timeout=10.0) as client:
            response = await client.get(self._URL, params={"q": query})
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for block in soup.select(".result__body")[:max_results]:
            title_tag = block.select_one(".result__a")
            if not title_tag:
                continue
            snippet_tag = block.select_one(".result__snippet")
            results.append(SearchResult(
                title=title_tag.get_text(strip=True),
                url=title_tag.get("href", ""),
                snippet=snippet_tag.get_text(strip=True) if snippet_tag else "",
            ))
        return results

@lru_cache
def get_search_engine() -> SearchEngine:
    settings = get_llm_settings()
    if settings.llm_web_search_engine == "duckduckgo":
        return DuckDuckGoSearchEngine()
    raise ValueError(f"Unknown web search engine: {settings.llm_web_search_engine}")    