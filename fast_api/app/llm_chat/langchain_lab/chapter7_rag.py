"""
Chapter 7 — RAG: retrieval (Ch6) + generation (Ch2), replacing ask_with_rag()/answer_with_context().

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter7_rag
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.llm_chat.config import get_llm_settings
from app.llm_chat.schemas import RagAskResponse, RagSource

RAG_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the reference "
    "material provided. If the context doesn't contain the answer, say so."
)


def format_context(docs_with_scores) -> str:
    return "\n\n".join(f"[{i + 1}] {doc.page_content}" for i, (doc, _score) in enumerate(docs_with_scores))


def main() -> None:
    settings = get_llm_settings()

    embeddings = OpenAIEmbeddings(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_embedding_model,
        check_embedding_ctx_length=False,
    )
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )

    # --- Ch6: index (same as before) ---
    store = InMemoryVectorStore(embeddings)
    store.add_texts(
        [
            "The Eiffel Tower was completed in 1889 for the World's Fair.",
            "It is 330 meters tall including antennas.",
            "The tower is located in Paris, on the Champ de Mars.",
            "Mount Everest is the tallest mountain above sea level.",
        ],
        metadatas=[
            {"document_id": 1, "chunk_index": 0},
            {"document_id": 1, "chunk_index": 1},
            {"document_id": 1, "chunk_index": 2},
            {"document_id": 2, "chunk_index": 0},
        ],
    )

    question = "How tall is the Eiffel Tower, and when was it built?"

    # --- Step 1: retrieve (replaces embed_texts(question) + find_similar()) ---
    matches = store.similarity_search_with_score(question, k=2)

    if not matches:
        response = RagAskResponse(question=question, answer="I don't have enough relevant information.", sources=[])
    else:
        # --- Step 2: build context + generate (replaces build_rag_context() + answer_with_context()) ---
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            ("user", "{context}\n\nQuestion: {question}"),
        ])
        answer_chain = prompt | llm | StrOutputParser()

        answer = answer_chain.invoke({"context": format_context(matches), "question": question})
        print(answer)
        # --- Step 3: same RagAskResponse shape your endpoint already returns ---
        response = RagAskResponse(
            question=question,
            answer=answer,
            sources=[
                RagSource(
                    document_id=doc.metadata.get("document_id"),
                    chunk_index=doc.metadata.get("chunk_index"),
                    similarity=score,
                    text=doc.page_content,
                )
                for doc, score in matches
            ],
        )

    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()