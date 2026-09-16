import ast
import operator

from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session

from .schemas import EmbedRequest
from .utils.web_search import get_search_engine

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


@tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return the numeric result."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Error evaluating expression: {e}"


def make_search_documents_tool(db: Session, embeddings: OpenAIEmbeddings):
    @tool
    async def search_documents(query: str) -> str:
        """Search the user's uploaded documents for relevant text. Use this for any
        question about document- or company-specific information you would not
        otherwise know."""
        from .service import embed_texts, find_similar
        embed_result = await embed_texts(EmbedRequest(input=query), embeddings)
        matches = find_similar(db, embed_result.embeddings[0], limit=3, min_similarity=0.65)
        if not matches:
            return "No relevant documents found."
        return "\n\n".join(
            f"[{i + 1}] {row.source_text}" for i, (row, _similarity) in enumerate(matches)
        )
    return search_documents


@tool
async def web_search(query: str) -> str:
    """Search the public web for current information. Use this for anything outside
    your training data or the user's own documents — current events, prices,
    external specs, public policies, etc."""
    engine = get_search_engine()
    try:
        results = await engine.search(query)
    except Exception as e:
        return f"Error performing web search: {e}"
    if not results:
        return "No web results found."
    return "\n\n".join(
        f"[{i + 1}] {r.title} ({r.url})\n{r.snippet}" for i, r in enumerate(results)
    )