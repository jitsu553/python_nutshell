"""
Chapter 3 — Structured output: get a validated Pydantic object back, not raw text.
Foreshadows Chapter 7: this is the shape we'll want a RAG answer to have.

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter3_structured_output
"""

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.llm_chat.config import get_llm_settings


class RagAnswer(BaseModel):
    answer: str = Field(description="The answer, based only on the given context.")
    confidence: Literal["low", "medium", "high"] = Field(
        description="How well the context actually supports the answer."
    )
    cited_sources: list[int] = Field(
        description="0-based indices of the context chunks actually used."
    )


CONTEXT = """
[0] The Eiffel Tower was completed in 1889 for the World's Fair.
[1] It is 330 meters tall including antennas.
[2] The tower is located in Paris, on the Champ de Mars.
"""


def main() -> None:
    settings = get_llm_settings()

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )

    structured_llm = llm.with_structured_output(RagAnswer)

    result = structured_llm.invoke( 
        f"Context:\n{CONTEXT}\nQuestion: How tall is the Eiffel Tower, and when was it built?"
    )

    print(result)
    print(type(result))
    print(result.answer, "|", result.confidence, "|", result.cited_sources)


if __name__ == "__main__":
    main()