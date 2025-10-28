#### NOT WORKING ####
# Weird import error on create_tool_calling_agent



import os
from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage
#from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor 
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END

# Import the tools from your tools.py file
from .tools import get_patient_data

# --- Set your OpenAI API Key ---
# Make sure to set this in your environment variables
# os.environ["OPENAI_API_KEY"] = "sk-..."
# if not os.environ.get("OPENAI_API_KEY"):
#     print("Warning: OPENAI_API_KEY not set.")

# 1. Define the Agent's State
class AgentGraphState(TypedDict):
    """
    This is the state that will be passed between nodes in the graph.
    """
    messages: List[BaseMessage]  # The chat history
    user_id: str                 # The user this chat belongs to
    patient_id: Optional[str]    # The patient context, if any

# 2. Setup LLM and Tools
# CUSTOMIZE FOR YOUR MODEL
llm = ChatOllama(model="deepseek-r1:8b", temperature=0)
tools = [get_patient_data] # A list of all tools the agent can use

# 3. Create the Agent
# This prompt tells the agent its purpose and how to behave
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are 'Bariatric GPT', a helpful medical assistant for doctors. "
     "Your user is a doctor (user_id: {user_id}). "
     "You are currently discussing patient (patient_id: {patient_id}). "
     "Only use your tools if you need to fetch new data. "
     "Be concise, professional, and helpful."),
    MessagesPlaceholder(variable_name="messages"),
    MessagesPlaceholder(variable_name="agent_scratchpad"), # Where the agent "thinks"
])

# create_openai_tools_agent creates the core "runnable"
agent_runnable = create_tool_calling_agent(llm, tools, prompt)

# AgentExecutor wraps the runnable and handles the tool-calling loop
# This is our complete agent.
agent_executor = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True  # Set to True for debugging agent steps
)

# 4. Define the Graph Nodes
# We will have one main node: the agent itself.
async def run_agent(state: AgentGraphState):
    """
    This node invokes the agent executor.
    The AgentExecutor will internally handle the loop of:
    LLM -> call tool -> LLM -> final answer
    """
    print(f"--- Running agent for user: {state['user_id']} ---")
    
    # The agent_executor takes the state as input
    result = await agent_executor.ainvoke(state)
    
    # We update the state with the agent's final output message
    return {"messages": state["messages"] + [result["output"]]}

# 5. Build the Graph
workflow = StateGraph(AgentGraphState)

# Add the single agent node
workflow.add_node("agent", run_agent)

# Set the entry point
workflow.set_entry_point("agent")

# The agent is the only node, so it's also the end
workflow.add_edge("agent", END)

# Compile the graph into a runnable application
app = workflow.compile()

print("--- LangGraph App Compiled Successfully! ---")