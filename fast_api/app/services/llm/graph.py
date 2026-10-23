from fastapi import FastAPI, Request
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt
from app.services.llm.tool_registry import requires_approval, not_asked
import logging
import time
log = logging.getLogger(__name__)

RECURSION_LIMIT = 15
CHECKPOINTER_APP_STATE_KEY = "llm_checkpointer"
CHECKPOINTER_CTX_APP_STATE_KEY = "_llm_checkpointer_ctx"  # keeps the async context manager alive


def _checkpointer_dsn() -> str:
    from app.core.config import get_settings
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")


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

def build_agent_graph(llm: ChatOpenAI, tools: list, checkpointer,
                      prechecks: dict | None = None, on_tool_error=None):
    prechecks = prechecks or {}
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    async def call_model(state: MessagesState) -> dict:
        t0 = time.perf_counter()
        response = await llm_with_tools.ainvoke(state["messages"])
        usage = response.usage_metadata or {}
        log.info("llm_call ms=%d in_tokens=%s out_tokens=%s tool_calls=%s",
                 (time.perf_counter() - t0) * 1000, usage.get("input_tokens"),
                 usage.get("output_tokens"), [c["name"] for c in response.tool_calls])
        return {"messages": [response]}

    def precheck(call: dict) -> str | None:
        fn = prechecks.get(call["name"])
        if fn is None:
            return None
        try:
            return fn(call["args"])
        except Exception as e:  # missing or unexpected arguments
            return f"Invalid arguments for {call['name']}: {e}"

    async def approval_gate(state: MessagesState) -> dict:
        calls = state["messages"][-1].tool_calls
        risky = [c for c in calls if requires_approval(c["name"])]
        if not risky:
            return {}
        humans = [str(m.content).lower() for m in state["messages"] if m.type == "human"][-3:]
        errors = {c["id"]: err for c in risky if (err := not_asked(c["name"], humans) or precheck(c))}
        if errors:  # doomed action: skip the human, let the model fix it
            return {"messages": [
                ToolMessage(content=errors.get(c["id"], "Not run: another action in this step was "
                                                        "invalid. Fix it and call this one again."),
                            tool_call_id=c["id"], name=c["name"])
                for c in calls
            ]}
        decision = interrupt({
            "action": ", ".join(c["name"] for c in risky),
            "calls": [{"name": c["name"], "args": c["args"]} for c in risky],
        })
        if decision.get("approved"):
            return {}
        reason = decision.get("reason") or "no reason given"
        return {"messages": [
            ToolMessage(content=f"Rejected by the human reviewer. Reason: {reason}. "
                                "Revise if appropriate; do not resend it unchanged.",
                        tool_call_id=c["id"], name=c["name"])
            for c in calls
        ]}

    def after_gate(state: MessagesState) -> str:
        return "call_model" if state["messages"][-1].type == "tool" else "tools"

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_edge(START, "call_model")
    if tools:
        graph.add_node("approval_gate", approval_gate)
        graph.add_node("tools", ToolNode(tools, handle_tool_errors=on_tool_error or True))
        graph.add_conditional_edges("call_model", tools_condition, {"tools": "approval_gate", END: END})
        graph.add_conditional_edges("approval_gate", after_gate, {"call_model": "call_model", "tools": "tools"})
        graph.add_edge("tools", "call_model")
    else:
        graph.add_edge("call_model", END)
    return graph.compile(checkpointer=checkpointer)