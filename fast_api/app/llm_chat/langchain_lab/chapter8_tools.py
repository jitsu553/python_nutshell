"""
Chapter 8 — Tools: @tool + bind_tools, replacing TOOLS list + TOOL_FUNCTIONS dispatch.

Run from fast_api/:
    python -m app.llm_chat.langchain_lab.chapter8_tools
"""

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.llm_chat.config import get_llm_settings
from app.llm_chat.tools import _eval_node
import ast


@tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return the numeric result."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Error evaluating expression: {e}"


def main() -> None:
    settings = get_llm_settings()

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_request_timeout_seconds,
    )

    llm_with_tools = llm.bind_tools([calculate])

    messages = [{"role": "user", "content": "What is 25 * 18, then add 7?"}]
    response = llm_with_tools.invoke(messages)

    print("tool_calls:", response.tool_calls)

    if response.tool_calls:
        messages.append(response)
        for call in response.tool_calls:
            result = calculate.invoke(call)   # returns a ToolMessage, tool_call_id already set
            print("tool result:", result , type(result))
            messages.append(result)

        final = llm_with_tools.invoke(messages)
        print("final answer:", final.content)
    else:
        print("model answered directly:", response.content)


if __name__ == "__main__":
    main()