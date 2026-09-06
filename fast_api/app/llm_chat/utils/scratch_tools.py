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
                    "expression": {"type": "string", "description": "e.g. '25 * 18'"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "word_count",
            "description": "Count the number of words in a piece of text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to count words in"}
                },
                "required": ["text"],
            },
        },
    },
]


def calculate(expression: str) -> str:
    # ponytail: eval() on arbitrary text is a real injection risk outside a throwaway script
    return str(eval(expression))


def word_count(text: str) -> str:
    return str(len(text.split()))


TOOL_FUNCTIONS = {"calculate": calculate, "word_count": word_count}


def call_ollama(messages):
    response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools},
        headers={"Authorization": "Bearer ollama"},
        timeout=60.0,
    )
    response.raise_for_status()
    response_data = response.json()
    print(json.dumps(response_data,indent=2))
    return response_data["choices"][0]["message"]


messages = [{
    "role": "user",
    "content": "What is 25 * 18? Also, how many words are in the sentence 'the quick brown fox jumps'?",
}]

while True:
    message = call_ollama(messages)

    if not message.get("tool_calls"):
        print(message["content"])
        break

    messages.append(message)
    

    for call in message["tool_calls"]:
        name = call["function"]["name"]
        args = json.loads(call["function"]["arguments"])
        print(f"  -> model called {name}({args})")

        result = TOOL_FUNCTIONS[name](**args)

        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })