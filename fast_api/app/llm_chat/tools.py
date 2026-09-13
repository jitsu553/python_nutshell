import ast
import operator
import httpx
from sqlalchemy.orm import Session

from .schemas import EmbedRequest
# from .service import embed_texts, find_similar

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

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


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")

async def calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Error evaluating expression: {e}"



async def search_documents(query: str, db: Session, client: httpx.AsyncClient) -> str:
    from .service import embed_texts, find_similar
    embed_result = await embed_texts(EmbedRequest(input=query), client)
    matches = find_similar(db, embed_result.embeddings[0], limit=3, min_similarity=0.5)

    if not matches:
        return "No relevant documents found."

    return "\n\n".join(
        f"[{i + 1}] {row.source_text}" for i, (row, _similarity) in enumerate(matches)
    )


TOOL_FUNCTIONS = {"calculate": calculate, "search_documents": search_documents}