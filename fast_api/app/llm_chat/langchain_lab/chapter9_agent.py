"""
Chapter 9 — Full agent loop with create_agent, replacing the manual
MAX_TOOL_ITERATIONS loop + tool_kwargs() dispatch in ChatService.send_message().

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter9_agent
"""

import ast
import asyncio
import json

import httpx
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.llm_chat.config import get_llm_settings
from app.llm_chat.schemas import EmbedRequest
from app.llm_chat.tools import _eval_node
from app.llm_chat.utils.web_search import get_search_engine


@tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return the numeric result."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Error evaluating expression: {e}"


def make_search_documents_tool(db: Session, client: httpx.AsyncClient):
    @tool
    async def search_documents(query: str) -> str:
        """Search the user's uploaded documents for relevant text. Use for
        anything document- or company-specific that you wouldn't otherwise know."""
        from app.llm_chat.service import embed_texts, find_similar

        embed_result = await embed_texts(EmbedRequest(input=query), client)
        matches = find_similar(db, embed_result.embeddings[0], limit=3, min_similarity=0.65)
        if not matches:
            return "No relevant documents found."
        return "\n\n".join(f"[{i + 1}] {row.source_text}" for i, (row, _sim) in enumerate(matches))

    return search_documents


@tool
async def web_search(query: str) -> str:
    """Search the public web for current information outside your training data."""
    engine = get_search_engine()
    try:
        results = await engine.search(query)
    except Exception as e:
        return f"Error performing web search: {e}"
    if not results:
        return "No web results found."
    return "\n\n".join(f"[{i + 1}] {r.title} ({r.url})\n{r.snippet}" for i, r in enumerate(results))


async def main() -> None:
    settings = get_llm_settings()

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )

    db = SessionLocal()
    async with httpx.AsyncClient(
        base_url=settings.llm_base_url,
        timeout=httpx.Timeout(settings.llm_request_timeout_seconds),
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
    ) as client:
        agent = create_agent(
            model=llm,
            tools=[calculate, make_search_documents_tool(db, client), web_search],
            system_prompt="You are a helpful assistant. Use tools when they help answer the question.",
        )

        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "What is 340 * 12? Also, who won the last FIFA World Cup?"}]
        })
        print(result)
        for message in result["messages"]:
            print(f"[{message.type}] {message.content}")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())