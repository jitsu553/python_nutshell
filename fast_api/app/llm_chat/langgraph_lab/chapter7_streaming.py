"""
Chapter 7 — Streaming: astream(stream_mode="messages") yields token-by-token
deltas as the model generates, instead of waiting for the full response.
Same idea as ChatService.send_message_stream() / format_sse() in your real router.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter7_streaming
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
    return graph.compile(checkpointer=MemorySaver())


async def main() -> None:
    app = build_graph()
    config = {"configurable": {"thread_id": "stream-demo"}, "recursion_limit": 10}

    async for chunk, metadata in app.astream(
        {"messages": [HumanMessage(content="What is 340 * 12? Also, who won the last FIFA World Cup?")]},
        config=config,
        stream_mode="messages",
    ):
        if metadata["langgraph_node"] != "call_model":
            continue   # only call_model runs a chat model; tools never emits text chunks
        if chunk.content:
            print(chunk.content, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())