"""
Chapter 9 — The real thing: ChatService.send_message()'s create_agent() tool loop,
rebuilt as an actual StateGraph. Everything around it (session lookup, RAG context,
history trimming, summarization, DB persistence) is reused from ChatService unchanged —
only the agent execution itself is replaced. No checkpointer: ChatSession/ChatMessage
in Postgres is already the persistence layer: build_session_messages() reloads history
every call, so a LangGraph checkpointer here would be a second, redundant memory system.

Run from fast_api/:
    python -m app.llm_chat.langgraph_lab.chapter9_chat_agent_graph
"""

import asyncio

import openai
from fastapi import HTTPException
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.db import SessionLocal
from app.llm_chat.config import get_llm_settings
from app.llm_chat.models import ChatMessage
from app.llm_chat.schemas import CreateSessionRequest
from app.llm_chat.service import ChatService, bind_overrides, llm_error_detail
from app.llm_chat.tools import calculate, make_search_documents_tool, web_search


def build_agent_graph(llm: ChatOpenAI, tools: list):
    """Same call_model / tools / loop shape as Chapter 5 — now parametrized per
    request via closure, since llm/tools differ per session (temperature overrides,
    a DB-bound search_documents tool) instead of being module-level constants."""
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: MessagesState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", tools_condition)
    graph.add_edge("tools", "call_model")
    return graph.compile()


async def send_message_via_langgraph(chat_service: ChatService, session_id: int, content: str) -> ChatMessage:
    """Same signature and behavior as ChatService.send_message() — compare the two
    side by side in service.py. Only the `if session.use_tools:` branch differs."""
    session = chat_service.get_session_or_404(session_id)

    chat_service.db.add(ChatMessage(session_id=session.id, role="user", content=content))
    chat_service.db.commit()

    messages = await chat_service.build_session_messages(session, content)
    llm = bind_overrides(chat_service.llm, session.temperature, session.max_tokens)

    try:
        if session.use_tools:
            tools = [calculate, make_search_documents_tool(chat_service.db, chat_service.embeddings), web_search]
            agent = build_agent_graph(llm, tools)
            result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": 15})

            assistant_message = None
            for msg in result["messages"][len(messages):]:
                if msg.type == "ai":
                    assistant_message = ChatMessage(
                        session_id=session.id, role="assistant", content=str(msg.content),
                        tool_calls=msg.tool_calls or None,
                        finish_reason=msg.response_metadata.get("finish_reason"),
                    )
                    chat_service.db.add(assistant_message)
                elif msg.type == "tool":
                    chat_service.db.add(ChatMessage(
                        session_id=session.id, role="tool", content=str(msg.content),
                        tool_call_id=msg.tool_call_id,
                    ))
        else:
            response = await llm.ainvoke(messages)
            assistant_message = ChatMessage(
                session_id=session.id, role="assistant", content=str(response.content),
                finish_reason=response.response_metadata.get("finish_reason"),
            )
            chat_service.db.add(assistant_message)
    except openai.APIError as exc:
        raise HTTPException(status_code=502, detail=llm_error_detail(exc))

    chat_service.db.commit()
    chat_service.db.refresh(assistant_message)
    return assistant_message


async def main() -> None:
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key,
        model=settings.llm_model, timeout=settings.llm_request_timeout_seconds,
    )
    embeddings = OpenAIEmbeddings(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key,
        model=settings.llm_embedding_model, check_embedding_ctx_length=False,
    )

    db = SessionLocal()
    chat_service = ChatService(db, llm, embeddings)
    session = chat_service.create_session(CreateSessionRequest(title="LangGraph lab ch9", use_tools=True))

    reply = await send_message_via_langgraph(
        chat_service, session.id, "What is 340 * 12? Also, who won the last FIFA World Cup?",
    )
    print(f"[{reply.role}] {reply.content}")

    for msg in chat_service.list_messages(session.id):
        print(f"  ({msg.role}) {msg.content[:80]}")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())