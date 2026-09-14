from langchain_openai import ChatOpenAI

from app.llm_chat.config import get_llm_settings


def main() -> None:
    settings = get_llm_settings()

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,   # same "http://localhost:11434/v1" as client.py
        api_key=settings.llm_api_key,     # same "ollama" placeholder
        model=settings.llm_model,         # same "mistral:latest"
        timeout=settings.llm_request_timeout_seconds,
    )

    response = llm.invoke("Say hello in exactly five words.")
    print(response)          # full AIMessage object
    print(response.content)  # just the text


if __name__ == "__main__":
    main()