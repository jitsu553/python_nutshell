import httpx
import json

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "mistral:latest"

tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a basic arithmetic expression and return the numeric result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A math expression, e.g. '25 * 18' or '(3 + 4) / 2'",
                    }
                },
                "required": ["expression"],
            },
        },
    }
]

response = httpx.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "Tell me a joke"}],
        # "messages": [{"role": "user", "content": "What is 25 * 18?"}],
        "tools": tools,
    },
    headers={"Authorization": "Bearer ollama"},
    timeout=60.0,
)
response.raise_for_status()

print(json.dumps(response.json(), indent=2))