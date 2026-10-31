import asyncio

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.services.llm.graph import build_agent_graph


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # the real model needs this; the fake ignores it
        return self


def make_agent(sent: list):
    @tool
    def send_email(to: str) -> str:
        """Send an email."""
        sent.append(to)
        return f"sent to {to}"

    replies = iter([
        AIMessage(content="", tool_calls=[{"name": "send_email", "args": {"to": "a@b.com"}, "id": "c1"}]),
        AIMessage(content="Done."),
    ])
    return build_agent_graph(FakeToolModel(messages=replies), [send_email], InMemorySaver())


def run(approved: bool):
    sent: list = []
    agent = make_agent(sent)
    cfg = {"configurable": {"thread_id": "t1"}}

    async def go():
        r = await agent.ainvoke({"messages": [HumanMessage(content="email a@b.com")]}, config=cfg)
        assert r["__interrupt__"][0].value["action"] == "send_email"  # paused at the gate
        assert sent == []                                            # nothing ran yet
        return await agent.ainvoke(Command(resume={"approved": approved, "reason": "no"}), config=cfg)

    return sent, asyncio.run(go())


def test_approved_tool_runs():
    sent, r = run(True)
    assert sent == ["a@b.com"] and r["messages"][-1].content == "Done."


def test_rejected_tool_never_runs():
    sent, r = run(False)
    assert sent == []