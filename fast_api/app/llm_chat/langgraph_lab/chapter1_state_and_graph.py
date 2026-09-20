"""
Chapter 1 — State, Nodes, Edges: the smallest possible LangGraph graph.
Compare to langchain_lab/chapter1_first_call.py — same single llm.invoke(),
now wrapped in graph plumbing that later chapters will grow.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter1_state_and_graph
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.llm_chat.config import get_llm_settings


class GraphState(TypedDict):
    question: str   # what goes in
    answer: str      # what a node fills in


def call_llm(state: GraphState) -> dict:
    """A node is just a function: state in, partial state update out."""
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    response = llm.invoke(state["question"])
    return {"answer": response.content}   # merged into state, not a full replacement


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("call_llm", call_llm)
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", END)
    return graph.compile()


def main() -> None:
    app = build_graph()
    result = app.invoke({"question": "Say hello in exactly five words."})
    print(result)          # full final state: {"question": ..., "answer": ...}
    print(result["answer"])


if __name__ == "__main__":
    main()