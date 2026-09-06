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


def calculate(expression: str) -> str:
    # ponytail: eval() on arbitrary text is a real injection risk outside a throwaway script —
    # a safe expression evaluator is the fix when this leaves scratch_tools.py
    result = eval(expression)
    return str(result)


messages = [{"role": "user", "content": "What is 25 * 18?"}]

response = httpx.post(
    OLLAMA_URL,
    json={"model": MODEL, "messages": messages, "tools": tools},
    headers={"Authorization": "Bearer ollama"},
    timeout=60.0,
)
response.raise_for_status()
data = response.json()
print(json.dumps(data, indent=2))
message = data["choices"][0]["message"]

if message.get("tool_calls"):
    messages.append(message)  # the assistant's tool-call turn goes into history too

    for call in message["tool_calls"]:
        args = json.loads(call["function"]["arguments"])
        result = calculate(**args)

        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })

    print(json.dumps(messages,indent=2))
    second_response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools},
        headers={"Authorization": "Bearer ollama"},
        timeout=60.0,
    )
    second_response.raise_for_status()
    final_message = second_response.json()["choices"][0]["message"]
    print(final_message["content"])
else:
    print(message["content"])