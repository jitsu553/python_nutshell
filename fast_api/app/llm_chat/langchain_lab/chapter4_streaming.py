"""
Chapter 4 — Streaming, replacing stream_chat_completion()'s manual SSE parsing.

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter4_streaming
"""

import asyncio

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.llm_chat.config import get_llm_settings


async def main() -> None:
    settings = get_llm_settings()

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )

    prompt = ChatPromptTemplate.from_messages([("user", "{user_prompt}")])
    chain = prompt | llm | StrOutputParser()

    async for chunk in chain.astream({"user_prompt": "Write two sentences about the ocean."}):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())