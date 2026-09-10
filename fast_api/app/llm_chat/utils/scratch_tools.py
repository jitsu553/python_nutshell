import asyncio
import json
import httpx

from app.db import SessionLocal
from app.llm_chat.config import get_llm_settings
from app.llm_chat.schemas import EmbedRequest
from app.llm_chat.service import embed_texts, find_similar

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "mistral:latest"
# run with python -m app.llm_chat.utils.scratch_tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a basic arithmetic expression and return the numeric result.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "e.g. '25 * 18'"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the user's uploaded documents for relevant text. "
                "Use this for any question about document- or company-specific information "
                "you would not otherwise know."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to search for"}},
                "required": ["query"],
            },
        },
    },
]


def calculate(expression: str) -> str:
    # ponytail: eval() on arbitrary text is a real injection risk outside a throwaway script
    return str(eval(expression))


def search_documents(query: str) -> str:
    settings = get_llm_settings()
    db = SessionLocal()
    print(settings.llm_base_url)
    try:
        async def _embed():
            async with httpx.AsyncClient(
                base_url="http://localhost:11434/v1",
                # base_url=settings.llm_base_url,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                timeout=60.0,
            ) as client:
                return await embed_texts(EmbedRequest(input=query), client)

        embed_result = asyncio.run(_embed())
        matches = find_similar(db, embed_result.embeddings[0], limit=3)

        if not matches:
            return "No relevant documents found."

        return "\n\n".join(
            f"[{i + 1}] {row.source_text}" for i, (row, _similarity) in enumerate(matches)
        )
    finally:
        db.close()


TOOL_FUNCTIONS = {"calculate": calculate, "search_documents": search_documents}


def call_ollama(messages):
    response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools},
        headers={"Authorization": "Bearer ollama"},
        timeout=60.0,
    )
    response.raise_for_status()
    response_data = response.json()
    # print(json.dumps(response_data,indent=2))
    return response_data["choices"][0]["message"]


messages = [{"role": "user", "content": "What does our leave policy say about sick leave?"}]

while True:
    message = call_ollama(messages)

    if not message.get("tool_calls"):
        print(message["content"])
        break

    messages.append(message)

    for call in message["tool_calls"]:
        name = call["function"]["name"]
        args = json.loads(call["function"]["arguments"])
        print(f"  -> model called {name}({args})")

        result = TOOL_FUNCTIONS[name](**args)

        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })