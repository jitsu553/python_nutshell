"""
Chapter 2 — Sequential nodes: state accumulates as it flows node -> node -> node.
Same shape as build_session_messages() -> llm.ainvoke() -> save-to-DB in
ChatService.send_message(), stripped to a skeleton.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter2_sequential_nodes
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.llm_chat.config import get_llm_settings


class GraphState(TypedDict):
    question: str             # input
    normalized_question: str  # set by normalize_question
    answer: str                # set by call_llm
    formatted_answer: str      # set by format_answer


def normalize_question(state: GraphState) -> dict:
    return {"normalized_question": state["question"].strip()}


def call_llm(state: GraphState) -> dict:
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    # reads a key written by the PREVIOUS node — this is the whole point of state
    response = llm.invoke(state["normalized_question"])
    return {"answer": response.content}


def format_answer(state: GraphState) -> dict:
    return {"formatted_answer": f"Assistant: {state['answer']}"}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("normalize_question", normalize_question)
    graph.add_node("call_llm", call_llm)
    graph.add_node("format_answer", format_answer)

    graph.add_edge(START, "normalize_question")
    graph.add_edge("normalize_question", "call_llm")
    graph.add_edge("call_llm", "format_answer")
    graph.add_edge("format_answer", END)
    return graph.compile()


def main() -> None:
    app = build_graph()
    result = app.invoke({"question": "  Say hello in exactly five words.  "})
    print(result)
    print(result["formatted_answer"])


if __name__ == "__main__":
    main()