import httpx
from sqlalchemy.orm import Session

from .schemas import EmbedRequest
from .service import embed_texts, find_similar

TOOLS = [
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


async def calculate(expression: str) -> str:
    # ponytail: eval() on arbitrary text is a real injection risk — hardened in Ch7
    return str(eval(expression))



async def search_documents(query: str, db: Session, client: httpx.AsyncClient) -> str:
    embed_result = await embed_texts(EmbedRequest(input=query), client)
    matches = find_similar(db, embed_result.embeddings[0], limit=3, min_similarity=0.5)

    if not matches:
        return "No relevant documents found."

    return "\n\n".join(
        f"[{i + 1}] {row.source_text}" for i, (row, _similarity) in enumerate(matches)
    )


TOOL_FUNCTIONS = {"calculate": calculate, "search_documents": search_documents}