"""
Chapter 3 — Conditional edges: the graph picks its own path based on state.
First piece of the target diagram: Analyze -> need info? -> Search / Answer.
search_stub is a placeholder — Chapter 4 swaps it for a real tool call.
Chapter 5 turns this into a loop (search_stub -> analyze again, instead of straight to call_llm).

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter3_conditional_edges
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.llm_chat.config import get_llm_settings

NEEDS_SEARCH_HINTS = ("latest", "today", "current", "news", "who won", "price of", "weather")


class GraphState(TypedDict):
    question: str
    needs_search: bool
    search_results: str
    answer: str


def analyze(state: GraphState) -> dict:
    """Decision node — does NOT answer, only decides what happens next."""
    question_lower = state["question"].lower()
    needs_search = any(hint in question_lower for hint in NEEDS_SEARCH_HINTS)
    return {"needs_search": needs_search}


def route_from_analyze(state: GraphState) -> str:
    """The path function: reads state, returns a label. Doesn't touch state itself."""
    return "search" if state["needs_search"] else "answer"


def search_stub(state: GraphState) -> dict:
    # Placeholder — Chapter 4 replaces this with your real web_search tool.
    return {"search_results": f"[stub search result for: {state['question']}]"}


def call_llm(state: GraphState) -> dict:
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    prompt = state["question"]
    if state.get("search_results"):
        prompt = f"Context: {state['search_results']}\n\nQuestion: {state['question']}"
    response = llm.invoke(prompt)
    return {"answer": response.content}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("analyze", analyze)
    graph.add_node("search_stub", search_stub)
    graph.add_node("call_llm", call_llm)

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        route_from_analyze,
        {"search": "search_stub", "answer": "call_llm"},
    )
    graph.add_edge("search_stub", "call_llm")   # both branches converge here
    graph.add_edge("call_llm", END)
    return graph.compile()


def main() -> None:
    app = build_graph()

    print("--- no search needed ---")
    print(app.invoke({"question": "Say hello in exactly five words."})["answer"])

    print("--- search needed ---")
    result = app.invoke({"question": "What's the latest news on FIFA?"})
    print(result["search_results"])
    print(result["answer"])


if __name__ == "__main__":
    main()