"""
Chapter 5 — Memory: auto-injected per-session history + token-budget trimming.
Replaces build_session_messages()'s history-stitching + trim_to_token_budget()/truncate_history().
(Summarization is intentionally NOT reimplemented here — see the explanation.)

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter5_memory
"""

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

from app.llm_chat.config import get_llm_settings

settings = get_llm_settings()

llm = ChatOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
    timeout=settings.llm_request_timeout_seconds,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder("history"),
    ("user", "{input}"),
])

chain = prompt | llm

# Stand-in for your ChatSession/ChatMessage tables — in-memory, keyed by session_id.
_store: dict[str, InMemoryChatMessageHistory] = {}


def get_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _store:
        _store[session_id] = InMemoryChatMessageHistory()
    return _store[session_id]


chain_with_history = RunnableWithMessageHistory(
    chain,
    get_history,
    input_messages_key="input",
    history_messages_key="history",
)


def main() -> None:
    config = {"configurable": {"session_id": "demo-session-1"}}

    r1 = chain_with_history.invoke({"input": "My name is Sujit."}, config=config)
    print("Bot:", r1.content)

    r2 = chain_with_history.invoke({"input": "What's my name?"}, config=config)
    print("Bot:", r2.content)

    # Trimming — direct replacement for trim_to_token_budget()/truncate_history()
    history = get_history("demo-session-1")
    trimmed = trim_messages(
        history.messages,
        max_tokens=30,
        token_counter=llm,        # uses the model's real tokenizer, not a char/4 guess
        strategy="last",          # keep most recent — same direction as your reversed() loop
        include_system=True,
    )
    print(f"\nFull history: {len(history.messages)} messages, trimmed to: {len(trimmed)}")


if __name__ == "__main__":
    main()