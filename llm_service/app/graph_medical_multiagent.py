"""
Multi-Agent Medical Assistant System for Bariatric GPT
Uses LangGraph to coordinate multiple specialized agents
"""

import os
from typing import TypedDict, List, Optional, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from .tools import get_patient_data
import json

# Feature flag: disable patient tools until profile data is implemented
ENABLE_PATIENT_TOOLS = False

# ==========================================
# 1. DEFINE STATE
# ==========================================

class MultiAgentState(TypedDict):
    """State shared across all agents"""
    messages: List[BaseMessage]
    user_id: str
    patient_id: Optional[str]
    profile: Optional[dict]
    next_agent: str  # Which agent should run next
    medical_response: Optional[str]  # Response from medical agent
    data_response: Optional[str]  # Response from data agent
    final_response: Optional[str]  # Final synthesized response

# ==========================================
# 2. SETUP LLM
# ==========================================

# Using llama3.2:3b for faster responses (5-10 seconds vs 60+ seconds)
# For better quality but slower: "llama3.1:8b" or "deepseek-r1:8b"
llm = ChatOllama(model="llama3.2:3b", temperature=0)

# ==========================================
# 3. SUPERVISOR AGENT (Router)
# ==========================================

async def supervisor_agent(state: MultiAgentState) -> dict:
    """
    Lightweight, rules-based router that never blocks chat.
    If patient tools are disabled or no patient_id is given, route to medical.
    """
    print("--- SUPERVISOR: Analyzing query ---")

    last_message = state["messages"][-1].content.lower()
    patient_id = state.get("patient_id")

    if not ENABLE_PATIENT_TOOLS or not patient_id:
        next_agent = "medical"
    else:
        # Simple heuristics to decide if data is needed
        needs_data_keywords = [
            "this patient", "their weight", "current weight", "bmi", "vitals",
            "surgery date", "labs", "records", "progress", "chart", "patient"
        ]
        needs_medical_keywords = [
            "should", "can i", "is it ok", "how do", "what are", "guideline",
            "recommend", "diet", "nutrition", "exercise", "recovery", "complication"
        ]

        needs_data = any(k in last_message for k in needs_data_keywords)
        needs_med = any(k in last_message for k in needs_medical_keywords)

        if needs_data and needs_med:
            next_agent = "both"
        elif needs_data:
            next_agent = "data"
        else:
            next_agent = "medical"

    print(f"--- SUPERVISOR: Routing to '{next_agent}' ---")

    return {
        "next_agent": next_agent,
        "messages": state["messages"]
    }

# ==========================================
# 4. MEDICAL KNOWLEDGE AGENT
# ==========================================

async def medical_agent(state: MultiAgentState) -> dict:
    """
    Handles general medical questions, provides guidance and best practices.
    Specializes in bariatric surgery and post-operative care.
    """
    print("--- MEDICAL AGENT: Processing query ---")
    
    last_message = state["messages"][-1].content
    
    medical_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a specialized medical assistant for bariatric surgery and weight management.

Your expertise includes:
- Bariatric surgery procedures (gastric bypass, sleeve gastrectomy, etc.)
- Post-operative care and recovery
- Nutrition guidelines for bariatric patients
- Weight loss management
- Complication prevention and management

Guidelines:
- Provide accurate, professional medical information
- Be concise and clear (2-3 sentences max)
- Always remind that this is general guidance, not a substitute for doctor consultation
- Use medical terminology but explain it simply

User's question: {query}"""),
    ])
    
    chain = medical_prompt | llm
    response = await chain.ainvoke({"query": last_message})
    
    medical_response = response.content
    print(f"--- MEDICAL AGENT: Response generated ---")
    
    return {
        "medical_response": medical_response,
        "messages": state["messages"]
    }

# ==========================================
# 5. DATA RETRIEVAL AGENT
# ==========================================

async def data_agent(state: MultiAgentState) -> dict:
    """
    Retrieves patient data from the database using tools.
    Only fetches data - does NOT interpret it.
    """
    print("--- DATA AGENT: Fetching patient data ---")
    
    patient_id = state.get("patient_id")

    if not ENABLE_PATIENT_TOOLS:
        data_response = (
            "Note: Patient-specific tools are disabled right now. "
            "I'll provide general guidance without accessing records."
        )
        print("--- DATA AGENT: Tools disabled (skipping DB fetch) ---")
        return {
            "data_response": data_response,
            "messages": state["messages"]
        }
    
    if not patient_id:
        # No patient context; return a neutral note so synthesizer can still respond well
        data_response = "Note: No patient ID provided. I will answer generally without personal data."
        print("--- DATA AGENT: No patient ID (skipping DB fetch) ---")
        return {
            "data_response": data_response,
            "messages": state["messages"]
        }
    
    # Use the tool to fetch patient data
    try:
        patient_data = await get_patient_data.ainvoke({"patient_id": patient_id})
        
        # Format the data nicely
        if isinstance(patient_data, dict) and "error" not in patient_data:
            data_response = f"Patient Data Retrieved:\n{json.dumps(patient_data, indent=2)}"
        else:
            # Graceful message when patient not found or storage error
            error_text = patient_data.get("error") if isinstance(patient_data, dict) else str(patient_data)
            data_response = (
                "Note: I couldn't access patient-specific data for this request. "
                "I'll provide general guidance instead."
                f"\nDetails: {error_text}"
            )
        
        print(f"--- DATA AGENT: Data retrieved for patient {patient_id} ---")
    
    except Exception as e:
        data_response = f"Error fetching patient data: {str(e)}"
        print(f"--- DATA AGENT: Error - {e} ---")
    
    return {
        "data_response": data_response,
        "messages": state["messages"]
    }

# ==========================================
# 6. RESPONSE SYNTHESIZER
# ==========================================

async def synthesizer_agent(state: MultiAgentState) -> dict:
    """
    Combines outputs from medical and/or data agents into a cohesive final response.
    """
    print("--- SYNTHESIZER: Combining responses ---")
    
    medical_resp = state.get("medical_response")
    data_resp = state.get("data_response")
    profile = state.get("profile") or {}
    last_message = state["messages"][-1].content
    lowerm = last_message.lower()

    # Quick path: if the user asks about their own preferences, return the stored profile directly
    profile_query_phrases = [
        "what are my food preferences",
        "what are my preferences",
        "what are my food preferences?",
        "what are my preferences?",
        "what is my profile",
        "show my profile",
        "what foods do i dislike",
        "my food preferences",
        "my profile",
    ]

    if any(phrase in lowerm for phrase in profile_query_phrases):
        # If profile exists, format it in a clear, short answer
        if profile:
            disliked = profile.get("disliked_foods") or []
            allergies = profile.get("allergies") or []
            diet_type = profile.get("diet_type") or "not specified"
            surgery_date = profile.get("surgery_date") or "not specified"

            parts = []
            parts.append(f"Diet type: {diet_type}.")
            if disliked:
                parts.append(f"Disliked foods: {', '.join(disliked)}.")
            else:
                parts.append("Disliked foods: none recorded.")
            if allergies:
                parts.append(f"Allergies/intolerances: {', '.join(allergies)}.")
            else:
                parts.append("Allergies/intolerances: none recorded.")
            parts.append(f"Surgery date: {surgery_date}.")

            final_response = " ".join(parts) + "\n\n(You can edit these in Settings → Edit Profile.)"

            return {
                "final_response": final_response,
                "messages": state["messages"] + [AIMessage(content=final_response)]
            }
        else:
            final_response = (
                "I don't have your profile data yet. You can set your food dislikes, allergies, diet type, and surgery date in Settings → Edit Profile. "
                "Once saved, ask again and I'll use that information to tailor meal suggestions."
            )
            return {
                "final_response": final_response,
                "messages": state["messages"] + [AIMessage(content=final_response)]
            }
    
    # Determine what we have to synthesize
    profile_summary = json.dumps(profile, indent=2) if profile else "(no profile provided)"

    if medical_resp and data_resp:
        synthesis_prompt = f"""
You are a helpful medical assistant synthesizer. You will produce ONLY the following three sections in plain text:

1) General Diet Suggestions:
- Provide strictly general dietary guidance relevant to bariatric patients (high-level principles only). Do NOT give personalized medical directives or specific medical treatment.

2) Example Meal Ideas:
- Create three sample meals (Breakfast, Lunch, Dinner). For each meal include a one-line description, approximate portions, and a one-line simple rationale. Use the user's `surgery_date` and `diet_type` to tailor meal complexity and texture (e.g., early post-op: softer, protein-focused; later: more variety). Honor disliked foods and allergies from the profile; if no profile is available, produce neutral, general meal ideas suitable for typical post-bariatric diets.

3) Suggested Questions for the Clinic:
- Provide 4-6 general, useful questions the user can ask their surgical team about bariatric surgery, recovery, nutrition, or follow-up care.

Context:
User question: "{last_message}"
Medical agent response:
{medical_resp}
Data agent response:
{data_resp}
User profile summary:
{profile_summary}

Tone and rules:
- Prioritize personalization: if profile data (diet_type, disliked_foods, allergies, surgery_date) is present, use it to adapt meal plans and examples.
- If unsure what to recommend for a given meal or phase, default to recommending protein-focused options (lean protein, dairy/protein shakes, legumes if tolerated) as a safe, post-bariatric-friendly choice.
- Keep language general and non-prescriptive. Always include a reminder that this is general information and not a substitute for medical advice.
- Be concise: overall output should be clear and skimmable (use bullets or short paragraphs).
- Do not reference patient identifiers or attempt diagnosis.

Generate the three sections now.
"""

    elif medical_resp:
        synthesis_prompt = f"""
You are a helpful medical assistant. Produce ONLY the following three sections in plain text:

1) General Diet Suggestions:
- Provide strictly general dietary guidance relevant to bariatric patients (high-level principles only).

2) Example Meal Ideas:
- Create three sample meals (Breakfast, Lunch, Dinner). Use the user's `surgery_date` and `diet_type` to tailor meal complexity and texture (e.g., early post-op: softer, protein-focused; later: more variety). Avoid any disliked foods or allergies if present in the profile.

3) Suggested Questions for the Clinic:
- Provide 4-6 useful questions the user can ask their surgical team.

Context:
User question: "{last_message}"
Medical agent response:
{medical_resp}
User profile summary:
{profile_summary}

Prioritize personalization: if profile data (diet_type, disliked_foods, allergies, surgery_date) is present, use it to adapt meal plans and examples. If unsure, default to protein-focused options. Keep it concise and non-prescriptive. Reminder: this is general information, not medical advice.
"""

    elif data_resp:
        synthesis_prompt = f"""
You are a helpful medical assistant producing general guidance and meal examples. Produce ONLY these three sections in plain text:

1) General Diet Suggestions
2) Example Meal Ideas (3 meals)
3) Suggested Questions for the Clinic (4-6 questions)

Context:
User question: "{last_message}"
Data agent response:
{data_resp}
User profile summary:
{profile_summary}

Prioritize personalization: if profile data (diet_type, disliked_foods, allergies, surgery_date) is present, use it to adapt meal plans and examples. If unsure, default to protein-focused options. Keep language general and concise. Do not provide personalized medical directives.
"""

    else:
        # Last-line fallback: directly answer the user's question with a concise medical response
        rescue_prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a helpful medical assistant specializing in bariatric surgery and weight management.
Provide accurate, concise guidance in 2-3 sentences. This is general information, not a substitute for medical care.
If you are unsure what to recommend, prioritize protein-rich options (lean protein, protein shakes, dairy or tolerated legumes) as safe post-bariatric choices.
"""),
            ("human", "{query}")
        ])

        chain = rescue_prompt | llm
        response = await chain.ainvoke({"query": last_message})
        final_response = response.content.strip()

        return {
            "final_response": final_response,
            "messages": state["messages"] + [AIMessage(content=final_response)]
        }
    
    response = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
    final_response = response.content.strip()

    print("--- SYNTHESIZER: Final response created ---")

    # Create an updated concise memory summary that preserves user preferences or notable events.
    try:
        prev_memory = state.get("memory") or ""
        memory_prompt = (
            f"You are a summarization assistant that writes one short sentence (<=25 words) to capture what is useful to remember about a user for future conversations.\n"
            f"Previous memory: {prev_memory}\n"
            f"Conversation snippet - User: \"{last_message}\" Assistant: \"{final_response}\"\n"
            "Create an updated memory that preserves persistent preferences (diet_type, disliked foods, allergies) and any recent user events (e.g., user ate a suggested meal). Keep it concise." 
        )

        mem_resp = await llm.ainvoke([HumanMessage(content=memory_prompt)])
        memory_summary = mem_resp.content.strip()
    except Exception as e:
        print(f"--- SYNTHESIZER: Memory generation failed: {e} ---")
        memory_summary = prev_memory if prev_memory else ""

    return {
        "final_response": final_response,
        "memory": memory_summary,
        "messages": state["messages"] + [AIMessage(content=final_response)]
    }

# ==========================================
# 7. ROUTING LOGIC
# ==========================================

def route_after_supervisor(state: MultiAgentState) -> str:
    """Determines which agent to call based on supervisor's decision"""
    next_agent = state.get("next_agent", "medical")
    
    if next_agent == "end":
        return "synthesizer"  # Go straight to end with a simple response
    elif next_agent == "medical":
        return "medical_agent"
    elif next_agent == "data":
        if not ENABLE_PATIENT_TOOLS:
            return "medical_agent"
        return "data_agent"
    elif next_agent == "both":
        if not ENABLE_PATIENT_TOOLS:
            return "medical_agent"
        return "medical_agent"  # Start with medical, then data
    else:
        return "medical_agent"  # Default

def route_after_medical(state: MultiAgentState) -> str:
    """After medical agent, check if we also need data agent"""
    if state.get("next_agent") == "both" and ENABLE_PATIENT_TOOLS:
        return "data_agent"
    else:
        return "synthesizer"

def route_after_data(state: MultiAgentState) -> str:
    """After data agent, always go to synthesizer"""
    return "synthesizer"

# ==========================================
# 8. BUILD THE GRAPH
# ==========================================

workflow = StateGraph(MultiAgentState)

# Add all agent nodes
workflow.add_node("supervisor", supervisor_agent)
workflow.add_node("medical_agent", medical_agent)
workflow.add_node("data_agent", data_agent)
workflow.add_node("synthesizer", synthesizer_agent)

# Set entry point
workflow.set_entry_point("supervisor")

# Add conditional edges from supervisor
workflow.add_conditional_edges(
    "supervisor",
    route_after_supervisor,
    {
        "medical_agent": "medical_agent",
        "data_agent": "data_agent",
        "synthesizer": "synthesizer"
    }
)

# Add conditional edges from medical agent
workflow.add_conditional_edges(
    "medical_agent",
    route_after_medical,
    {
        "data_agent": "data_agent",
        "synthesizer": "synthesizer"
    }
)

# Add edge from data agent to synthesizer
workflow.add_edge("data_agent", "synthesizer")

# Synthesizer is always the end
workflow.add_edge("synthesizer", END)

# Compile the graph
app = workflow.compile()

print("=" * 50)
print("✅ Multi-Agent Medical System Compiled Successfully!")
print("=" * 50)
print("Agents: Supervisor → Medical / Data → Synthesizer")
print("=" * 50)
