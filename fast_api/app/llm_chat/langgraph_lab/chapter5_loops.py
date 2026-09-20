"""
Chapter 5 — Loops: tools -> call_model instead of tools -> END.
This is the target diagram for real: Analyze -> need info? -> Search -> Analyze -> ... -> Answer.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter5_loops
"""
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.llm_chat.config import get_llm_settings
from app.llm_chat.tools import calculate, web_search

TOOLS = [calculate, web_search]

SYSTEM_PROMPT = SystemMessage(content=(
    "Only call a tool if the question genuinely requires arithmetic or "
    "current/external information. Otherwise answer directly in plain text. "
    "Once a tool has given you what you need, answer — do not call it again "
    "for the same information."
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
    graph.add_edge("tools", "call_model")   # <-- the whole chapter is this one line
    return graph.compile()


async def main() -> None:
    app = build_graph()

    result = await app.ainvoke(
        {"messages": [HumanMessage(content="What is 340 * 12? Also, who won the last FIFA World Cup?")]},
        config={"recursion_limit": 10},
    )
    for i, msg in enumerate(result["messages"]):
        print(f"#{i}# [{msg.type}] {msg.content}")


if __name__ == "__main__":
    asyncio.run(main())