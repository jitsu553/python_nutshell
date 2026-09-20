"""
Chapter 6 — Checkpoints: persist state across separate invoke() calls via thread_id.
MemorySaver is in-process only (gone on restart) — compare to ChatSession/ChatMessage
in Postgres, which is what production checkpointers (e.g. PostgresSaver) replace this with.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter6_checkpoints
"""

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.llm_chat.config import get_llm_settings
from app.llm_chat.tools import calculate, web_search

TOOLS = [calculate, web_search]

SYSTEM_PROMPT = SystemMessage(content=(
    "Only call a tool if the question genuinely requires arithmetic or "
    "current/external information. Otherwise answer directly in plain text."
))


def call_model(state: MessagesState) -> dict:
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    llm_with_tools = llm.bind_tools(TOOLS)
    response = llm_with_tools.invoke([SYSTEM_PROMPT] + state["messages"])
    return {"messages": [response]}


def build_graph():
    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", tools_condition)
    graph.add_edge("tools", "call_model")
    return graph.compile(checkpointer=MemorySaver())   # <-- the whole new concept


async def main() -> None:
    app = build_graph()
    thread_a = {"configurable": {"thread_id": "conversation-1"}, "recursion_limit": 10}

    # Turn 1 — only message we send is this one.
    result = await app.ainvoke({"messages": [HumanMessage(content="What is 340 * 12?")]}, config=thread_a)
    print("--- turn 1 ---")
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")

    # Turn 2 — same thread_id, and we DON'T resend the first question.
    # The checkpointer loads turn 1's saved state first; "it" refers back to that.
    result = await app.ainvoke({"messages": [HumanMessage(content="Divide that result by 8.")]}, config=thread_a)
    print("--- turn 2 (same thread) ---")
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")

    # A different thread_id is a completely separate conversation — no memory of thread_a.
    thread_b = {"configurable": {"thread_id": "conversation-2"}, "recursion_limit": 10}
    result = await app.ainvoke({"messages": [HumanMessage(content="Divide that result by 8.")]}, config=thread_b)
    print("--- different thread (no memory of conversation-1) ---")
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")


if __name__ == "__main__":
    asyncio.run(main())