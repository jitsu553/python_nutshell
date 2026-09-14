"""
Chapter 2 — Prompt templates + LCEL, replacing build_messages()/build_payload().

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter2_prompt_templates
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.llm_chat.config import get_llm_settings


def main() -> None:
    settings = get_llm_settings()

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )

    # Equivalent of build_messages(): a template instead of manual dict-appending.
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("user", "{user_prompt}"),
    ])

    # Equivalent of build_payload() + httpx.post() + parsing choices[0].message.content
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({
        "system_prompt": "You are a terse assistant. Follow word-count instructions exactly.",
        "user_prompt": "Say hello in exactly five words.",
    })

    print(result)
    print(type(result))  # plain str now, not an AIMessage


if __name__ == "__main__":
    main()