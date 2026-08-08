from fastapi import APIRouter, Depends, HTTPException
import httpx

from .client import get_llm_client
from .config import get_llm_settings
from .schemas import PromptRequest, PromptResponse

router = APIRouter(prefix="/llm-chat", tags=["llm-chat"])


@router.post("/prompt", response_model=PromptResponse)
async def send_prompt(
    body: PromptRequest,
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> PromptResponse:
    settings = get_llm_settings()

    messages = []
    if body.system_prompt:
        messages.append({"role": "system", "content": body.system_prompt})
    messages.append({"role": "user", "content": body.prompt})

    payload = {
        "model": settings.llm_model,
        "messages": messages,
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens

    try:
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach LLM server: {exc}")

    data = response.json()
    choice = data["choices"][0]
    reply = choice["message"]["content"]
    finish_reason = choice.get("finish_reason")

    return PromptResponse(
        model=settings.llm_model,
        prompt=body.prompt,
        reply=reply,
        finish_reason=finish_reason,
    )