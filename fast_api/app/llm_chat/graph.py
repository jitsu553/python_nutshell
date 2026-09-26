from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

RECURSION_LIMIT = 15


def build_agent_graph(llm: ChatOpenAI, tools: list):
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    async def call_model(state: MessagesState) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        print("TOOLS BOUND:", bool(tools), "| tool_calls:", response.tool_calls, "| content:", str(response.content)[:200])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_edge(START, "call_model")
    if tools:
        graph.add_node("tools", ToolNode(tools))
        graph.add_conditional_edges("call_model", tools_condition)
        graph.add_edge("tools", "call_model")
    else:
        graph.add_edge("call_model", END)
    return graph.compile()  # no checkpointer: Postgres is the source of truth