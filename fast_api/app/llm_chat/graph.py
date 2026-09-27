from fastapi import FastAPI, Request
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

RECURSION_LIMIT = 15
CHECKPOINTER_APP_STATE_KEY = "llm_checkpointer"
CHECKPOINTER_CTX_APP_STATE_KEY = "_llm_checkpointer_ctx"  # keeps the async context manager alive


def _checkpointer_dsn() -> str:
    from app.db import DATABASE_URL
    return DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


async def connect_checkpointer(app: FastAPI) -> None:
    ctx = AsyncPostgresSaver.from_conn_string(_checkpointer_dsn())
    checkpointer = await ctx.__aenter__()
    await checkpointer.setup()
    setattr(app.state, CHECKPOINTER_APP_STATE_KEY, checkpointer)
    setattr(app.state, CHECKPOINTER_CTX_APP_STATE_KEY, ctx)


async def close_checkpointer(app: FastAPI) -> None:
    ctx = getattr(app.state, CHECKPOINTER_CTX_APP_STATE_KEY, None)
    if ctx is not None:
        await ctx.__aexit__(None, None, None)


def get_checkpointer(request: Request):
    checkpointer = getattr(request.app.state, CHECKPOINTER_APP_STATE_KEY, None)
    if checkpointer is None:
        raise RuntimeError("Checkpointer is not initialized on app.state")
    return checkpointer

def build_agent_graph(llm: ChatOpenAI, tools: list, checkpointer):
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    async def call_model(state: MessagesState) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        print("TOOLS BOUND:", bool(tools), "| tool_calls:", response.tool_calls, "| content:", str(response.content)[:200])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_edge(START, "call_model")
    if tools:
        graph.add_node("tools", ToolNode(tools))
        graph.add_conditional_edges("call_model", tools_condition)
        graph.add_edge("tools", "call_model")
    else:
        graph.add_edge("call_model", END)
    return graph.compile(checkpointer=checkpointer)  # no checkpointer: Postgres is the source of truth