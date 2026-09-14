"""
Chapter 6 — Embeddings + vector store, replacing embed_texts()/store_embedding()/find_similar().
In-memory for now; your real setup (Postgres + pgvector) maps to langchain_postgres.PGVector later —
same interface, different backend, one-line swap.

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter6_embeddings
"""

from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from app.llm_chat.config import get_llm_settings


def main() -> None:
    settings = get_llm_settings()

    embeddings = OpenAIEmbeddings(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_embedding_model,       # "nomic-embed-text" — same model embed_texts() uses
        check_embedding_ctx_length=False,          # skip OpenAI-tokenizer-based length checks; Ollama isn't OpenAI
    )

    store = InMemoryVectorStore(embeddings)

    # Equivalent of calling store_embedding() once per chunk — metadata mirrors your
    # document_id/chunk_index columns on TextEmbedding.
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

    # Equivalent of find_similar() (which runs TextEmbedding.embedding.cosine_
    results = store.similarity_search_with_score("How tall is the Eiffel Tower?", k=2)

    for doc, score in results:
        print(f"{score:.4f}  {doc.metadata}  {doc.page_content}")


if __name__ == "__main__":
    main()