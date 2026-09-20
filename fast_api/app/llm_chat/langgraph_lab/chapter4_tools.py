"""
Chapter 4 — Tools + ToolNode: wire in your real tools from app/llm_chat/tools.py.
Stops right after the tool runs (no hand-back to the model yet) — that loop is Chapter 5.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter4_tools
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.llm_chat.config import get_llm_settings
from app.llm_chat.tools import calculate, web_search

TOOLS = [calculate, web_search]


def call_model(state: MessagesState) -> dict:
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    llm_with_tools = llm.bind_tools(TOOLS)
    messages = [SystemMessage(content=(
        "Only call a tool if the question genuinely requires arithmetic or "
        "current/external information. Otherwise answer directly in plain text."
    ))] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}   # appended, not overwritten — see explanation below


def build_graph():
    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", tools_condition)   # prebuilt path function
    graph.add_edge("tools", END)   # stops here for now — Chapter 5 loops this back
    return graph.compile()


def main() -> None:
    app = build_graph()

    print("--- needs a tool ---")
    result = app.invoke({"messages": [HumanMessage(content="What is 340 * 12?")]})
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")

    print("--- no tool needed ---")
    result = app.invoke({"messages": [HumanMessage(content="Say hello in exactly five words.")]})
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")


if __name__ == "__main__":
    main()