"""
Chapter 8 — Human-in-the-loop: interrupt() pauses the graph before a tool runs,
resumes later with Command(resume=...). Requires a checkpointer (state must persist
across the pause). Insert human_review between "does the model want a tool?" and
actually running one.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter8_human_in_the_loop
"""

import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

from app.llm_chat.config import get_llm_settings
from app.llm_chat.tools import calculate, web_search

TOOLS = [calculate, web_search]

SYSTEM_PROMPT = SystemMessage(content=(
    "Only call a tool if the question genuinely requires arithmetic or "
    "current/external information. Otherwise answer directly in plain text."
))


class ReviewState(MessagesState):
    tool_approved: bool


def call_model(state: ReviewState) -> dict:
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


def human_review(state: ReviewState) -> dict:
    """Runs BEFORE any tool executes. Everything above interrupt() re-runs on
    resume — keep it side-effect-free (no DB writes, no API calls up here)."""
    # print("json.dumps(state,indent=2)")
    # print(state)
    last_message = state["messages"][-1]
    decision = interrupt({
        "pending_tool_calls": [
            {"name": c["name"], "args": c["args"]} for c in last_message.tool_calls
        ],
    })
    if decision == "approve":
        return {"tool_approved": True}

    rejections = [
        ToolMessage(content="Tool call rejected by user.", tool_call_id=c["id"])
        for c in last_message.tool_calls
    ]
    return {"tool_approved": False, "messages": rejections}


def route_after_review(state: ReviewState) -> str:
    return "tools" if state["tool_approved"] else "call_model"


def build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("call_model", call_model)
    graph.add_node("human_review", human_review)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", tools_condition, {"tools": "human_review", END: END})
    graph.add_conditional_edges("human_review", route_after_review, {"tools": "tools", "call_model": "call_model"})
    graph.add_edge("tools", "call_model")
    return graph.compile(checkpointer=MemorySaver())


async def main() -> None:
    app = build_graph()
    config = {"configurable": {"thread_id": "approval-demo222"}, "recursion_limit": 10}

    result = await app.ainvoke({"messages": [HumanMessage(content="What is 340 * 12?")]}, config=config)

    if "__interrupt__" in result:
        pending = result["__interrupt__"][0].value
        print("PAUSED — awaiting approval for:", pending)
        # Standing in for a real human clicking "approve" in your UI:
        result = await app.ainvoke(Command(resume="approve"), config=config)

    print("--- final state ---")
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")


if __name__ == "__main__":
    asyncio.run(main())