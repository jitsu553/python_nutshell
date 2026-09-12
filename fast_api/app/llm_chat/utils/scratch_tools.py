import asyncio
import json
import httpx

from app.db import SessionLocal
from app.llm_chat.config import get_llm_settings
from app.llm_chat.tools import TOOLS, TOOL_FUNCTIONS

# run with python -m app.llm_chat.utils.scratch_tools

async def call_ollama(client: httpx.AsyncClient, settings, messages: list[dict]) -> dict:
    response = await client.post("/chat/completions", json={
        "model": settings.llm_model,
        "messages": messages,
        "tools": TOOLS,
    })
    response.raise_for_status()
    return response.json()["choices"][0]["message"]


async def run_agent_loop(messages: list[dict]) -> None:
    settings = get_llm_settings()
    db = SessionLocal()
    try:
        async with httpx.AsyncClient(
            base_url=settings.llm_base_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=60.0,
        ) as client:
            while True:
                message = await call_ollama(client, settings, messages)

                if not message.get("tool_calls"):
                    print(message["content"])
                    return

                messages.append(message)

                for call in message["tool_calls"]:
                    name = call["function"]["name"]
                    args = json.loads(call["function"]["arguments"])
                    print(f"  -> model called {name}({args})")

                    fn = TOOL_FUNCTIONS[name]
                    kwargs = {"db": db, "client": client} if name == "search_documents" else {}
                    result = await fn(**args, **kwargs)

                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    finally:
        db.close()


if __name__ == "__main__":
    messages = [{"role": "user", "content": "What is 25 * 18, and what does our leave policy say about sick leave?"}]
    asyncio.run(run_agent_loop(messages))