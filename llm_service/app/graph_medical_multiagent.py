"""
Multi-Agent Medical Assistant System for Bariatric GPT
Uses LangGraph to coordinate multiple specialized agents in a sequential pipeline:
1. Preprocessor (Expand shorthand)
2. Researcher (RAG / Knowledge Retrieval)
3. Nurse (Patient Data / Logging)
4. Synthesis (Doctor / Final Response)
"""

import os
from datetime import datetime
from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from .tools import get_patient_data, record_meal
from .rag import query_knowledge
import json

# ==========================================
# 1. DEFINE STATE
# ==========================================

class MultiAgentState(TypedDict):
    """State shared across all agents"""
    messages: List[BaseMessage]
    user_id: str
    patient_id: Optional[str]
    profile: Optional[dict]
    conversation_log: Optional[str]
    clinical_context: Optional[str]  # Facts from Researcher
    data_response: Optional[str]     # Report from Nurse
    memory: Optional[str]            # Previous memory summary

# ==========================================
# 2. SETUP LLM
# ==========================================

# Using local Ollama model (gemma3:1b or llama3 recommended)
llm = ChatOllama(model="llama3", temperature=0)

SYSTEM_PERSONA = (
    "You are a warm, empathetic bariatric care assistant. You speak naturally, like a knowledgeable friend. "
    "Be concise but caring. Do not repeat generic offers of help constantly. "
    "If the user says 'thanks', just say 'You're welcome' without extra fluff.\n\n"
    "CRITICAL RULES:\n"
    "1. DO NOT ask the user what they ate today unless they explicitly ask you to log a meal.\n"
    "2. FOCUS on future guidance. Use their past history to inform advice, but don't interrogate them about the present.\n"
    "3. If you don't understand, ask clarifying questions about their GOAL, not their intake."
)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def _calculate_post_op_phase(surgery_date_str: str) -> str:
    if not surgery_date_str or surgery_date_str.lower() == "not specified":
        return ""
    try:
        surgery_date = datetime.fromisoformat(surgery_date_str.split('T')[0])
    except ValueError:
        return ""

    delta = datetime.now() - surgery_date
    weeks = delta.days // 7
    
    if weeks < 0:
        return f"PRE-OP (Surgery in {abs(weeks)} weeks)"
    elif weeks == 0:
        return "PHASE 1: Clear Liquids (Week 1)"
    elif weeks == 1:
        return "PHASE 2: Full Liquids (Week 2)"
    elif 2 <= weeks < 4:
        return f"PHASE 3: Pureed/Soft Foods (Week {weeks+1})"
    elif 4 <= weeks < 8:
        return f"PHASE 4: Adaptive/Regular Soft Diet (Week {weeks+1})"
    else:
        return f"MAINTENANCE PHASE (Week {weeks+1})"

async def generate_and_persist_memory(user_id: str, prev_memory: str, last_message: str, assistant_response: str):
    """Background task to generate updated memory."""
    if not user_id:
        return
    try:
        memory_prompt = (
            f"Produce an UPDATED conversation memory as a JSON object (single JSON value).\n"
            f"Previous memory: {prev_memory}\n"
            f"User: \"{last_message}\"\nAssistant: \"{assistant_response}\"\n"
            "Requirements: Return ONLY valid JSON keys: preferences, recent_meals, last_recommendations."
        )
        mem_resp = await llm.ainvoke([HumanMessage(content=memory_prompt)])
        new_memory = mem_resp.content.strip()
        
        # Clean markdown
        if "```json" in new_memory:
            new_memory = new_memory.split("```json")[1].split("```")[0].strip()
        elif "```" in new_memory:
            new_memory = new_memory.split("```")[1].split("```")[0].strip()

        # Save to Storage Service (Hardcoded URL for now)
        import httpx
        STORAGE_URL = "http://localhost:8002" 
        async with httpx.AsyncClient() as client:
            await client.put(f"{STORAGE_URL}/me/{user_id}/memory", json={"memory": new_memory})
        
    except Exception as e:
        print(f"❌ Memory update failed: {e}")

# ==========================================
# 4. AGENTS
# ==========================================

# 4.1 PREPROCESSOR
async def preprocessor_agent(state: MultiAgentState) -> dict:
    """Expands shorthand user replies."""
    messages = state.get("messages", [])
    if not messages:
        return {}
    
    last_user = messages[-1].content.strip()
    # Simple heuristic for shorthand
    tokens = last_user.lower().split()
    is_shorthand = len(tokens) <= 3 and any(t in ["yes", "no", "1", "2", "option"] for t in tokens)
    
    if is_shorthand:
        # Just pass through for now, or implement expansion if needed. 
        # For this refactor, we focus on the core pipeline.
        pass
        
    return {}

# 4.2 RESEARCHER (RAG)
async def research_agent(state: MultiAgentState) -> dict:
    """Queries Knowledge Base for clinical facts."""
    messages = state.get("messages", [])
    if not messages:
        return {"clinical_context": ""}
        
    last_message = messages[-1].content
    # Skip casual greetings
    if len(last_message) < 5 or last_message.lower().strip() in ["hi", "hello", "thanks"]:
        return {"clinical_context": ""}
        
    print(f"--- RESEARCHER: Searching knowledge for '{last_message}' ---")
    context = query_knowledge(last_message, n_results=5)
    
    if context:
        print(f"--- RESEARCHER: Found {len(context)} chars of context ---")
        return {"clinical_context": context}
    else:
        print("--- RESEARCHER: No relevant docs found ---")
        return {"clinical_context": ""}

# 4.3 NURSE (PATIENT DATA)
async def patient_data_agent(state: MultiAgentState) -> dict:
    """Handles meal logging and profile data retrieval."""
    messages = state.get("messages", [])
    if not messages:
        return {"data_response": ""}

    last_message = messages[-1].content
    low = last_message.lower().strip()
    user_id = state.get("user_id")
    profile = state.get("profile") or {}
    data_response = ""

    is_record_meal = any(k in low for k in ["log meal", "track meal", "record meal", "add meal", "i ate", "i had", "i just ate"]) and len(low) > 10
    is_profile_request = any(k in low for k in ["my profile", "my stats", "surgery date", "allergies"])
    
    # 1. Logging
    if is_record_meal and user_id:
        nutrition_prompt = f"""
        Extract meal details from: "{last_message}"
        Format:
        MEAL: [description]
        PROTEIN: [grams]
        CALORIES: [kcal]
        """
        try:
            resp = await llm.ainvoke([HumanMessage(content=nutrition_prompt)])
            text = resp.content.strip()
            import re
            m_meal = re.search(r'MEAL:\s*(.+)', text)
            m_prot = re.search(r'PROTEIN:\s*(\d+(?:\.\d+)?)', text)
            m_cal = re.search(r'CALORIES:\s*(\d+(?:\.\d+)?)', text)
            
            if m_meal and m_prot and m_cal:
                meal_name = m_meal.group(1).strip()
                result = await record_meal.ainvoke({
                    "user_id": user_id,
                    "meal_name": meal_name,
                    "protein_grams": float(m_prot.group(1)),
                    "calories": float(m_cal.group(1))
                })
                if result.get("success"):
                    data_response = f"ACTION_TAKEN: Logged {meal_name}. Daily Total: {result.get('protein_total')}g protein."
                else:
                    data_response = f"ACTION_FAILED: {result.get('error')}"
        except Exception as e:
            data_response = f"ACTION_FAILED: Classification error {e}"

    # 2. Data Context (Always provide if available)
    parts = []
    if profile:
        parts.append(f"Surgery Date: {profile.get('surgery_date', 'N/A')}")
        parts.append(f"Diet: {profile.get('diet_type', 'N/A')}")
        if profile.get('allergies'):
            parts.append(f"Allergies: {', '.join(profile.get('allergies'))}")
    
    if is_profile_request:
        data_response = (data_response + "\n" if data_response else "") + "PATIENT_FILE_REQUESTED:\n" + "\n".join(parts)
    elif parts and not data_response:
        data_response = "PATIENT_CONTEXT:\n" + "\n".join(parts)
        
    return {"data_response": data_response}

# 4.4 SYNTHESIS (DOCTOR)
async def assistant_agent(state: MultiAgentState) -> dict:
    """Synthesizes final response using Research + Nurse Data."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    profile = state.get("profile") or {}
    prev_memory = state.get("memory") or ""
    convo_excerpt = state.get("conversation_log") or "[]"
    
    clinical_context = state.get("clinical_context") or ""
    data_response = state.get("data_response") or ""
    
    # Contexts
    phase_info = _calculate_post_op_phase(profile.get("surgery_date"))
    status_context = f"Patient Status: {phase_info}" if phase_info else ""
    
    # Prompt Construction
    prefix = ""
    if status_context:
        prefix += status_context + "\n"
    if clinical_context:
        prefix += f"\n[CLINICAL GUIDELINES]\n{clinical_context}\n"
    if data_response:
        prefix += f"\n[NURSE REPORT]\n{data_response}\n"
        
    prefix += "\n[INSTRUCTION]\nSynthesize a helpful response. Use Guidelines for safety. Use Nurse Report for actions/data.\n"
    
    full_text = prefix + "\nUser Question: " + last_message if prefix else last_message
    
    # Greeting Check
    greetings = ("hi", "hello", "hey", "good morning")
    if any(last_message.lower().startswith(g) for g in greetings) and len(last_message.split()) < 4:
        final_response = "Hello! I'm your bariatric assistant. How can I help you today?"
    else:
        try:
            resp = await llm.ainvoke([SystemMessage(content=SYSTEM_PERSONA), HumanMessage(content=full_text)])
            final_response = resp.content
        except Exception:
            final_response = "I'm having trouble thinking right now. Please try again."

    # Logging Helper (Compact)
    try:
        parsed = json.loads(convo_excerpt) if isinstance(convo_excerpt, str) else {}
        recent_user = parsed.get("recent_user_prompts", [])
        recent_assistant = parsed.get("recent_assistant_responses", [])
        recent_user.append(last_message)
        recent_assistant.append(final_response)
        new_log = json.dumps({
            "recent_user_prompts": recent_user[-5:],
            "recent_assistant_responses": recent_assistant[-5:]
        })
    except Exception:
        new_log = "[]"

    # Markdown Helper
    final_response_readme = f"# Assistant Response\n\n{final_response}\n\n_Generated by Bariatric-GPT_"

    return {
        "final_response": final_response,
        "final_response_readme": final_response_readme,
        "messages": messages + [AIMessage(content=final_response)],
        "conversation_log": new_log
    }

# ==========================================
# 5. WORKFLOW
# ==========================================

workflow = StateGraph(MultiAgentState)
workflow.add_node("preprocessor", preprocessor_agent)
workflow.add_node("researcher", research_agent)
workflow.add_node("nurse", patient_data_agent)
workflow.add_node("assistant", assistant_agent)

workflow.set_entry_point("preprocessor")
workflow.add_edge("preprocessor", "researcher")
workflow.add_edge("researcher", "nurse")
workflow.add_edge("nurse", "assistant")
workflow.add_edge("assistant", END)

app = workflow.compile()
print("✅ Sequential Agent System Compiled!")
