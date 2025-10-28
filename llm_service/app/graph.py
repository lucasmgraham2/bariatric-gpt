# --- File: llm_service/app/graph.py ---
# MODIFIED to be a simple chatbot without tools

import os
from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END

# --- Removed Imports ---
# We no longer need AgentExecutor, create_tool_calling_agent, or tools.py
# from langchain.agents import ...
# from .tools import get_patient_data

# 1. Define the Agent's State (No change)
class AgentGraphState(TypedDict):
    messages: List[BaseMessage]
    user_id: str
    patient_id: Optional[str]

# 2. Setup LLM (Simplified)
llm = ChatOllama(model="deepseek-r1:8b", temperature=0)
# We no longer need the 'tools' list

# 3. Create the Prompt (Simplified)
# We remove the 'agent_scratchpad' placeholder because there's no tool logic.
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are 'Bariatric GPT', a helpful medical assistant for doctors. "
     "Your user is a doctor (user_id: {user_id}). "
     "Be concise, professional, and helpful."),
    MessagesPlaceholder(variable_name="messages"),
])

# 4. Create a Simple "Chain"
# Instead of a complex agent, we just "chain" the prompt and the LLM together.
# This is a simple runnable that takes the state and returns an AI message.
simple_chain = prompt | llm

# 5. Define the Graph Node (Simplified)
async def run_chatbot(state: AgentGraphState):
    """
    This node now just runs the simple prompt-to-LLM chain.
    """
    print(f"--- Running simple chatbot for user: {state['user_id']} ---")
    
    # We invoke the simple chain with the current state
    result = await simple_chain.ainvoke(state)
    
    # The 'result' is the AI's response message. We add it to the state.
    return {"messages": state["messages"] + [result]}

# 6. Build the Graph (No change)
workflow = StateGraph(AgentGraphState)

# Add the node (we'll rename it for clarity)
workflow.add_node("chatbot", run_chatbot)

# Set the entry point
workflow.set_entry_point("chatbot")

# The chatbot is the only node, so it's also the end
workflow.add_edge("chatbot", END)

# Compile the graph into a runnable application
app = workflow.compile()

print("--- LangGraph App Compiled Successfully (Simple Chatbot Mode) ---")