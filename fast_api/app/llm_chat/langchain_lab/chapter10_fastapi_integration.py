"""
Chapter 10 — FastAPI integration: lifespan-managed agent + SSE streaming.
Standalone demo app on its own port — your real router.py/client.py are untouched.

Run from fast_api/:
    uvicorn app.llm_chat.langchain_lab.chapter10_fastapi_integration:app --reload --port 8010

Then, in another terminal:
    curl -N -X POST http://localhost:8010/agent/stream \
         -H "Content-Type: application/json" \
         -d "{\"message\": \"What is 340 * 12?\"}"
"""

import ast
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.llm_chat.config import get_llm_settings
from app.llm_chat.service import format_sse
from app.llm_chat.tools import _eval_node

AGENT_APP_STATE_KEY = "lc_agent"


@tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return the numeric result."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Error evaluating expression: {e}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    # Built once at startup — same idea as connect_llm_client() storing one
    # shared httpx.AsyncClient on app.state, instead of per-request.
    agent = create_agent(model=llm, tools=[calculate], system_prompt="You are a helpful assistant.")
    setattr(app.state, AGENT_APP_STATE_KEY, agent)
    yield


app = FastAPI(lifespan=lifespan)


def get_agent(request: Request):
    agent = getattr(request.app.state, AGENT_APP_STATE_KEY, None)
    if agent is None:
        raise RuntimeError("Agent is not initialized on app.state")
    return agent


class AgentMessageRequest(BaseModel):
    message: str


@app.post("/agent/stream")
async def agent_stream(body: AgentMessageRequest, agent=Depends(get_agent)):
    async def event_generator():
        async for chunk, _metadata in agent.astream(
            {"messages": [{"role": "user", "content": body.message}]},
            stream_mode="messages",
        ):
            if chunk.content:
                yield format_sse({"delta": chunk.content})
        yield format_sse({}, event="done")

    return StreamingResponse(event_generator(), media_type="text/event-stream")