from .config import get_llm_settings
from .schemas import PromptRequest


def build_messages(body: PromptRequest) -> list[dict]:
    messages = []
    if body.system_prompt:
        messages.append({"role": "system", "content": body.system_prompt})
    messages.append({"role": "user", "content": body.prompt})
    return messages


def build_payload(body: PromptRequest, *, stream: bool = False) -> dict:
    settings = get_llm_settings()

    payload = {
        "model": settings.llm_model,
        "messages": build_messages(body),
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens
    if stream:
        payload["stream"] = True

    return payload