"""
Multi-Agent Medical Assistant System for Bariatric GPT
Uses LangGraph to coordinate multiple specialized agents in a sequential pipeline:
1. Preprocessor (Expand shorthand)
2. Researcher (RAG / Knowledge Retrieval)
3. Nurse (Patient Data / Logging)
4. Synthesis (Doctor / Final Response)
"""

import os
import re
from datetime import datetime
from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from .tools import get_patient_data, record_meal
from .rag import query_knowledge
import json
import httpx

# Service URLs
STORAGE_URL = os.getenv("STORAGE_URL", "http://localhost:8002")

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

# Using local Ollama model (llama3) with sufficient context for conversation history
llm = ChatOllama(
    model="llama3",
    temperature=0,
    num_ctx=8192,
    num_predict=512
)

# Performance tuning
RAG_RESULTS = 1
MAX_GUIDELINE_CHARS = 400

SYSTEM_PERSONA = (
    "You are a warm, empathetic bariatric care assistant. You speak naturally, like a knowledgeable friend. "
    "Be concise but caring. Do not repeat generic offers of help constantly. "
    "If the user says 'thanks', just say 'You're welcome' without extra fluff.\n\n"
    "CRITICAL RULES:\n"
    "1. When the user references 'it', 'that', 'your suggestion', or asks follow-up questions, refer to what you said earlier in this conversation.\n"
    "2. DO NOT ask the user what they ate today unless they explicitly ask you to log a meal.\n"
    "3. FOCUS on future guidance. Use their past history to inform advice, but don't interrogate them.\n"
    "4. When suggesting meals, avoid recommending any meal already logged today.\n"
    "5. Prioritize answering the user's current question directly."
)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def _simplify_meal_name(meal_name: str) -> str:
    name = (meal_name or "").strip()
    name = re.sub(r"^[\"'\[]+|[\"'\]]+$", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"^(a|an|the|some|my)\s+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+please\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(
        r"\s+(today|tonight|this morning|this afternoon|for (breakfast|lunch|dinner|snack))$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    return name.strip(" .,!;:")

async def _meal_intent_agent_llm(message: str) -> dict:
    """Use LLM to detect meal intent (eating or recording a meal)."""
    low = (message or "").lower().strip()
    if not low:
        return {"intent": "none"}
    
    intent_prompt = f"""Analyze this user message and determine their intent about meal logging.
    
User message: "{message}"

IMPORTANT: Ignore greetings and pleasantries (hi, thanks, please) - focus on the core intent.
Example: "I ate chicken soup, thanks" → intent is "eating", meal is "chicken soup"

Classify the intent as ONE of:
1. "eating" - User says they ate/had a meal (extract what they ate)
2. "recording" - User asks to record/log/save/add a meal
3. "referential" - User refers to a prior suggestion (using "that", "it", "your suggestion")
4. "none" - Not about eating or recording meals (just greetings, questions, etc.)

If intent is "eating" or "recording", extract what food they mentioned.

Respond EXACTLY in this format:
INTENT: [eating|recording|referential|none]
MEAL: [specific food name or "ref" if referential or "none" if no meal]"""

    try:
        resp = await llm.ainvoke([HumanMessage(content=intent_prompt)])
        text = resp.content.strip()
        print(f"--- MEAL_INTENT_LLM Response ---\n{text}\n--- END ---")
        
        m_intent = re.search(r'INTENT:\s*(eating|recording|referential|none)', text, re.IGNORECASE)
        m_meal = re.search(r'MEAL:\s*(.+?)(?=\n|$)', text, re.IGNORECASE | re.DOTALL)
        
        if m_intent:
            intent_type = m_intent.group(1).lower()
            meal_text = m_meal.group(1).strip() if m_meal else ""
            
            if intent_type in ("eating", "recording"):
                if meal_text.lower() in ("ref", "none", "reference", "referential"):
                    return {"intent": "referential"}
                return {"intent": intent_type, "meal_text": meal_text}
            elif intent_type == "referential":
                return {"intent": "referential"}
            else:
                return {"intent": "none"}
    except Exception as e:
        print(f"--- MEAL_INTENT_LLM Error: {e}, falling back to patterns ---")
    
    return {"intent": "none"}

async def _meal_extraction_agent_llm(message: str, meal_text: str, conversation_history: str) -> dict:
    """Use LLM to intelligently extract, simplify meal name, and estimate macros using conversation context."""
    if not meal_text:
        return {"meal_name": "", "protein": 0.0, "calories": 0.0}
    
    extraction_prompt = f"""Extract the SPECIFIC FOOD ITEM name and estimate macros.

User message: "{message}"
Meal text: "{meal_text}"

Recent conversation:
{conversation_history}

INSTRUCTIONS:
1. Extract ONLY the actual food/dish name mentioned ("chicken soup", "protein shake", "greek yogurt")
2. Remove articles (a, an, the) and portions (small, large, bowl of)
3. Use the exact food they described, not a generic term
4. Estimate realistic macros for ONE bariatric-sized portion (early post-op patients eat small amounts):
   - Protein: typically 5-30g for most meals (up to 40g for high protein items like shakes)
   - Calories: typically 100-400 kcal for most meals (up to 600 kcal for larger meals)
5. ALWAYS provide all three values. Never output "None" or leave blank.

Examples:
- "I ate a protein shake" → MEAL_NAME: protein shake, PROTEIN: 25, CALORIES: 180
- "I had chicken soup" → MEAL_NAME: chicken soup, PROTEIN: 15, CALORIES: 200
- "scrambled eggs" → MEAL_NAME: scrambled eggs, PROTEIN: 12, CALORIES: 150
- "small greek yogurt" → MEAL_NAME: greek yogurt, PROTEIN: 10, CALORIES: 120

Respond EXACTLY in this format (fill all fields):
MEAL_NAME: [specific food name]
PROTEIN: [number between 5-40]
CALORIES: [number between 100-600]"""

    try:
        resp = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
        text = resp.content.strip()
        print(f"--- MEAL_EXTRACTION_LLM Response ---\n{text}\n--- END ---")
        
        m_name = re.search(r'MEAL_NAME:\s*(.+?)(?=\n|$)', text, re.IGNORECASE | re.DOTALL)
        m_prot = re.search(r'PROTEIN:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        m_cal = re.search(r'CALORIES:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        
        meal_name = m_name.group(1).strip() if m_name else meal_text
        protein = float(m_prot.group(1)) if m_prot else 0.0
        calories = float(m_cal.group(1)) if m_cal else 0.0
        
        meal_name = _simplify_meal_name(meal_name) if meal_name else ""
        
        return {"meal_name": meal_name, "protein": protein, "calories": calories}
    except Exception as e:
        print(f"--- MEAL_EXTRACTION_LLM Error: {e}, using fallback simplification ---")
        return {"meal_name": _simplify_meal_name(meal_text), "protein": 0.0, "calories": 0.0}

async def _resolve_meal_log_with_llm(message: str, last_assistant_response: str, conversation_history: str = "") -> dict:
    """Resolve meal logging using AI agents."""
    intent_result = await _meal_intent_agent_llm(message)
    intent = intent_result.get("intent", "none")
    
    if intent == "referential":
        candidates = _extract_candidate_meals_from_response(last_assistant_response)
        if candidates:
            return {
                "is_meal_log": True,
                "meal_name": _simplify_meal_name(candidates[0]),
                "candidate_meals": candidates,
                "is_referential": True,
                "protein": 0.0,
                "calories": 0.0,
            }
        return {"is_meal_log": False, "meal_name": "", "candidate_meals": [], "is_referential": True, "protein": 0.0, "calories": 0.0}
    
    if intent in ("eating", "recording"):
        meal_text = intent_result.get("meal_text", "")
        if meal_text:
            extraction_result = await _meal_extraction_agent_llm(message, meal_text, conversation_history)
            extracted_meal_name = extraction_result.get("meal_name", _simplify_meal_name(meal_text))
            extracted_protein = extraction_result.get("protein", 0.0)
            extracted_calories = extraction_result.get("calories", 0.0)
            
            return {
                "is_meal_log": True,
                "meal_name": extracted_meal_name,
                "candidate_meals": [],
                "is_referential": False,
                "protein": extracted_protein,
                "calories": extracted_calories,
            }
    
    return {"is_meal_log": False, "meal_name": "", "candidate_meals": [], "is_referential": False, "protein": 0.0, "calories": 0.0}



def _extract_candidate_meals_from_response(text: str) -> List[str]:
    if not text:
        return []

    candidates = []
    # Bullet or list style
    for line in text.splitlines():
        m = re.match(r"\s*[-*•]\s+(.+)", line)
        if m:
            item = m.group(1).strip().rstrip(".")
            if 3 <= len(item) <= 150:
                candidates.append(item)

    # Sentence-based suggestions (expanded patterns)
    suggestion_patterns = [
        r"(?:try|consider|suggest|recommend|how about|what about|you could have|you could try|idea:?)\s+([^.;\n]{3,150})",
        r"(?:good option|great choice|perfect choice)(?:\s+would be|\s+is)?\s+([^.;\n]{3,150})",
    ]
    for pattern in suggestion_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            item = match.group(1).strip().rstrip(".")
            # Clean up leading articles and connectors
            item = re.sub(r"^(a|an|the|some)\s+", "", item, flags=re.IGNORECASE)
            if 3 <= len(item) <= 150:
                candidates.append(item)

    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for item in candidates:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(item)
    
    print(f"--- EXTRACT: Found {len(ordered)} candidate meals: {ordered[:3]} ---")
    return ordered[:5]

# ==========================================
# 4. AGENTS
# ==========================================

# 4.1 RESEARCHER (RAG)
async def research_agent(state: MultiAgentState) -> dict:
    """Queries Knowledge Base for clinical facts."""
    messages = state.get("messages", [])
    if not messages:
        return {"clinical_context": ""}
        
    last_message = messages[-1].content
    low = last_message.lower().strip()
    skip_prefixes = ["hi", "hello", "thanks", "thank you", "bye"]
    if len(last_message) < 12 or any(low.startswith(p) for p in skip_prefixes):
        return {"clinical_context": ""}
    
    context = query_knowledge(last_message, n_results=RAG_RESULTS)
    return {"clinical_context": context if context else ""}

# 4.2 NURSE (PATIENT DATA)
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
    convo_excerpt = state.get("conversation_log") or "[]"

    # Parse conversation log once
    try:
        parsed = json.loads(convo_excerpt) if convo_excerpt and convo_excerpt != "[]" else {}
    except Exception:
        parsed = {}
    
    last_assistant_response = (parsed.get("recent_assistant_responses") or [""])[-1]
    is_profile_request = any(k in low for k in ["my profile", "my stats", "surgery date", "allergies"])
    
    # 1. Logging (AI intent + extraction + macro resolution)
    if user_id and len(low) > 6:
        # Build conversation history for context
        conversation_history = ""
        try:
            recent_user = parsed.get("recent_user_prompts", [])
            recent_assistant = parsed.get("recent_assistant_responses", [])
            for u, a in zip(recent_user[-3:], recent_assistant[-3:]):
                conversation_history += f"User: {u}\nAssistant: {a}\n"
        except:
            pass
        
        resolved = await _resolve_meal_log_with_llm(last_message, last_assistant_response, conversation_history)
        is_meal_log = resolved.get("is_meal_log", False)
        meal_name = resolved.get("meal_name", "")
        is_referential = resolved.get("is_referential", False)
        candidate_meals = resolved.get("candidate_meals", [])
        extracted_protein = resolved.get("protein", 0.0)
        extracted_calories = resolved.get("calories", 0.0)

        # Extract user-provided macros
        m_user_prot = re.search(r'(\d+(?:\.\d+)?)\s*(g|grams)?\s*protein', low)
        m_user_cal = re.search(r'(\d+(?:\.\d+)?)\s*(kcal|calories|calorie)', low)
        user_protein = float(m_user_prot.group(1)) if m_user_prot else 0.0
        user_calories = float(m_user_cal.group(1)) if m_user_cal else 0.0

        try:
            # Macro priority: user-provided > AI extraction agent
            protein_grams = user_protein if user_protein > 0 else extracted_protein
            calories = user_calories if user_calories > 0 else extracted_calories

            if is_meal_log and meal_name:
                try:
                    result = await record_meal.ainvoke({
                        "user_id": user_id,
                        "meal_name": meal_name,
                        "protein_grams": protein_grams,
                        "calories": calories
                    })
                    if result.get("success"):
                        protein_note = f"{user_protein}g" if user_protein > 0 else f"estimated {protein_grams}g" if protein_grams > 0 else "not provided"
                        calories_note = f"{user_calories} kcal" if user_calories > 0 else f"estimated {calories} kcal" if calories > 0 else "not provided"
                        data_response = f"Logged {meal_name}. Protein: {protein_note}. Calories: {calories_note}. Daily total: {result.get('protein_total')}g protein."
                    else:
                        data_response = f"Unable to log meal: {result.get('error')}"
                except Exception as e:
                    data_response = f"Unable to log meal: {str(e)}"
        except Exception as e:
            data_response = f"Unable to log meal: {str(e)}"
        
    # 2. Add patient profile context if requested
    if is_profile_request and profile:
        profile_info = f"Surgery Date: {profile.get('surgery_date', 'N/A')}\nDiet: {profile.get('diet_type', 'N/A')}"
        if profile.get('allergies'):
            profile_info += f"\nAllergies: {', '.join(profile.get('allergies'))}"
        data_response = (data_response + "\n" if data_response else "") + "PATIENT_FILE_REQUESTED:\n" + profile_info
    elif profile and not data_response:
        profile_info = f"Surgery Date: {profile.get('surgery_date', 'N/A')}\nDiet: {profile.get('diet_type', 'N/A')}"
        if profile.get('allergies'):
            profile_info += f"\nAllergies: {', '.join(profile.get('allergies'))}"
        data_response = "PATIENT_CONTEXT:\n" + profile_info
        
    return {"data_response": data_response}

# 4.4 SYNTHESIS (DOCTOR)
async def assistant_agent(state: MultiAgentState) -> dict:
    """Synthesizes final response using Research + Nurse Data."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    low_message = last_message.lower().strip()
    profile = state.get("profile") or {}
    convo_excerpt = state.get("conversation_log") or "[]"
    
    clinical_context = state.get("clinical_context") or ""
    data_response = state.get("data_response") or ""
    
    # Prompt Construction - Add contextual data to help the LLM respond
    parts = []
    
    # Clinical guidelines
    if clinical_context:
        truncated = clinical_context[:MAX_GUIDELINE_CHARS]
        parts.append(f"[GUIDELINES]\n{truncated}")
    include_todays_meals = any(
        phrase in low_message
        for phrase in [
            "recommend",
            "suggest",
            "meal ideas",
            "what should i eat",
            "dinner ideas",
            "lunch ideas",
            "breakfast ideas",
            "snack ideas",
            "log",
            "record",
            "add meal",
            "today's meals",
            "todays meals",
        ]
    )

    todays_meals = profile.get("todays_meals") or []
    if include_todays_meals and todays_meals:
        meal_names = []
        for meal in todays_meals:
            if isinstance(meal, dict) and meal.get("food"):
                meal_names.append(str(meal.get("food")))
            elif isinstance(meal, str):
                meal_names.append(meal)
        if meal_names:
            parts.append("[CONTEXT: User's meals logged today]\n" + ", ".join(meal_names[:20]))
    if data_response:
        parts.append(f"[DATA]\n{data_response}\n[DATA_RULE]\nIf DATA shows a meal was logged, acknowledge it naturally in your response (e.g., 'Got it, I've logged...'). Otherwise, use DATA only if directly relevant.")
    
    # Build system message with persona and context
    system_content = SYSTEM_PERSONA
    if parts:
        system_content += "\n\n" + "\n\n".join(parts)
    
    # Greeting Check
    greetings = ("hi", "hello", "hey", "good morning")
    if any(last_message.lower().startswith(g) for g in greetings) and len(last_message.split()) < 4:
        final_response = "Hello! I'm your bariatric assistant. How can I help you today?"
    else:
        try:
            # Pass full conversation history to the LLM
            llm_messages = [SystemMessage(content=system_content)] + messages
            resp = await llm.ainvoke(llm_messages)
            final_response = resp.content
        except Exception:
            final_response = "I'm having trouble thinking right now. Please try again."

    # Build conversation log for next turn
    try:
        parsed = json.loads(convo_excerpt) if convo_excerpt and convo_excerpt != "[]" else {}
        recent_user = list(parsed.get("recent_user_prompts", []))
        recent_assistant = list(parsed.get("recent_assistant_responses", []))
    except:
        recent_user, recent_assistant = [], []
    
    recent_user.append(last_message)
    recent_assistant.append(final_response)
    
    new_log = json.dumps({
        "recent_user_prompts": recent_user[-5:],
        "recent_assistant_responses": recent_assistant[-5:]
    })

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
workflow.add_node("researcher", research_agent)
workflow.add_node("nurse", patient_data_agent)
workflow.add_node("assistant", assistant_agent)

workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "nurse")
workflow.add_edge("nurse", "assistant")
workflow.add_edge("assistant", END)

app = workflow.compile()
print("Sequential Agent System Compiled!")
