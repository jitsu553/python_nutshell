from fastapi import FastAPI, Request
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .config import get_llm_settings

LLM_APP_STATE_KEY = "llm_client"
EMBEDDINGS_APP_STATE_KEY = "embeddings_client"


async def connect_llm_client(app: FastAPI) -> None:
    settings = get_llm_settings()
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )
    embeddings = OpenAIEmbeddings(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_embedding_model,
        check_embedding_ctx_length=False,
    )
    setattr(app.state, LLM_APP_STATE_KEY, llm)
    setattr(app.state, EMBEDDINGS_APP_STATE_KEY, embeddings)


async def close_llm_client(app: FastAPI) -> None:
    pass


def get_llm_client(request: Request) -> ChatOpenAI:
    llm = getattr(request.app.state, LLM_APP_STATE_KEY, None)
    if llm is None:
        raise RuntimeError("LLM client is not initialized on app.state")
    return llm


def get_embeddings_client(request: Request) -> OpenAIEmbeddings:
    embeddings = getattr(request.app.state, EMBEDDINGS_APP_STATE_KEY, None)
    if embeddings is None:
        raise RuntimeError("Embeddings client is not initialized on app.state")
    return embeddings