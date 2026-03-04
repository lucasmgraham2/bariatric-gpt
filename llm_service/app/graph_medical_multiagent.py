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
import math
from datetime import datetime
from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from .tools import get_patient_data, record_meal, search_nutrition
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
    nutrition_context: Optional[str] # Facts from Dietitian
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
RAG_RESULTS = 3
MAX_GUIDELINE_CHARS = 400

SYSTEM_PERSONA = (
    "You are a warm, empathetic bariatric care assistant. You speak naturally, like a knowledgeable friend. "
    "Be concise but caring. Do not repeat generic offers of help constantly. "
    "If the user says 'thanks', just say 'You're welcome' without extra fluff.\n\n"
    "CRITICAL RULES:\n"
    "0. THINKING PROCESS: You MUST start your response with a hidden <thought> block. Inside this block, explicitly state the patient's Current Phase, Diet Type, Activity Level, and Texture Restrictions. Evaluate the safety of their request based on these factors before generating your actual response outside the block.\n"
    "1. When the user references 'it', 'that', 'your suggestion', or asks follow-up questions, refer to what you said earlier in this conversation.\n"
    "2. DO NOT ask the user what they ate today unless they explicitly ask you to log a meal.\n"
    "3. FOCUS on future guidance. Use their past history to inform advice, but don't interrogate them.\n"
    "4. When suggesting meals, avoid recommending any meal already listed in TODAYS_MEALS.\n"
    "4b. Avoid repeating meal ideas listed in RECENT_RECOMMENDATIONS unless the user explicitly asks to repeat them.\n"
    "4c. PRIORITIZE VARIETY: Never suggest the same protein or main ingredient twice in a row. If spinach or salmon were just suggested/eaten, pick a completely different protein and vegetable for variety (e.g., if salmon was eaten, suggest chicken or tofu instead; if spinach was eaten, suggest broccoli or kale). ALWAYS check [PRIMARY_INGREDIENTS_TO_AVOID_REPEATING] and [RECENTLY_SUGGESTED_INGREDIENTS_AVOID] and suggest something from a completely different category.\n"
    "5. Prioritize answering the user's current question directly.\n"
    "6. TEMPORAL AWARENESS: Use the 'Current Phase' data. If PRE-OP, STRICTLY ENFORCE the liver shrinking diet (low carb, low fat, high protein) and advise against heavy/cheat meals to reduce surgical risk, and remind them that ANY solid food exceptions are strictly prohibited. If Phase 1 (Clear Liquids) or Phase 2 (Full Liquids), explicitly forbid pureed or solid foods.\n"
    "7. ALLERGIES & DISLIKES: NEVER suggest foods the user is allergic to or dislikes. If they ask for an allergen, explicitly remind them of their allergy and firmly decline.\n"
    "8. FIRM BOUNDARIES: If the user requests a crunchy food (like chips, popcorn, or raw veggies) violating their Current Phase, Diet, or Allergies, you MUST firmly decline, and you MUST EXPLICITLY explain the physical danger using exact terms like 'sharp edges causing internal tearing', 'pouch stretching', or 'dumping syndrome'. Then provide a safe alternative tailored to their exact profile and texture restrictions.\n"
    "9. NUTRITION FACTS: If given exact nutrition data from OpenFoodFacts, explicitly format your response to include: 'Here are the exact macros from OpenFoodFacts:' to show the user you verified the data.\n"
    "10. ACTIVITY LEVEL: You MUST explicitly mention the user's Activity Level (Sedentary, Lightly Active, Active) in your response and adjust portion sizes, calorie targets, and hydration recommendations accordingly. NEVER ignore their activity level.\n"
    "11. VEGAN/VEGETARIAN CONSTRAINTS: Ensure NO meat/poultry products (like chicken or beef broth) are suggested to Vegetarians or Vegans. Standard diets have no meat restrictions.\n"
    "12. TEXTURE SAFETY (NUTS/SEEDS/CRUNCHY): Nuts, seeds, and any crunchy foods (like popcorn or chips) MUST be avoided in Phase 1, Phase 2, and PRE-OP. In Phase 3, nuts/seeds MUST be ground or pureed. Whole nuts/seeds and crunchy foods are entirely forbidden until Phase 4 or Maintenance.\n"
    "13. EMOTIONAL SUPPORT & PLATEAUS: If the user is frustrated by a weight loss stall or plateau, explicitly validate their feelings, explain that plateaus are a normal part of the bariatric journey, AND YOU MUST EXPLICITLY ASK THEM 'What do you usually consider comfort food?' BEFORE offering any specific alternatives or food suggestions in your response. Wait for their reply.\n"
    "14. MEAL LOGGING: When [DATA] shows ACTION_TAKEN or ACTION_FAILED for a meal, simply confirm what was logged WITHOUT mentioning Current Phase, Diet info, or other context. Just acknowledge the action clearly and move forward.\n"
    "15. HIGH-PROTEIN FOCUS: When offering alternatives to unhealthy cravings or comfort foods, ALWAYS prioritize high-protein bariatric-friendly options (e.g., clear protein drinks in Phase 1, pureed high-protein dishes in Phase 3).\n"
    "16. CALORIE TARGETS: In early Phase 3 (Pureed/Soft), daily calorie goals are typically around 600-800. In Phase 4/5, it increases to 800-1200 depending on activity level. Do not push patients to 1000+ calories too early.\n"
    "17. OUT-OF-SCOPE QUERIES: You are strictly a Bariatric Care Assistant. If the user asks general life questions, coding questions, complex medical diagnostics unrelated to bariatric diet protocols, or political questions, politely decline and remind them of your purpose."
)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def _calculate_post_op_phase(surgery_date_str: str) -> str:
    if not surgery_date_str or surgery_date_str.lower() == "not specified":
        return ""
    surgery_date = None
    cleaned_date = str(surgery_date_str).strip().split('T')[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%y", "%m/%d/%y"):
        try:
            surgery_date = datetime.strptime(cleaned_date, fmt)
            # Handle 2-digit years (ensure 2000s)
            if surgery_date.year < 2000:
                surgery_date = surgery_date.replace(year=surgery_date.year + 2000)
            break
        except ValueError:
            continue
    if surgery_date is None:
        try:
            surgery_date = datetime.fromisoformat(cleaned_date)
        except ValueError:
            return ""

    now = datetime.now()
    delta = now - surgery_date
    weeks = delta.days // 7
    days_until_surgery = (surgery_date.date() - now.date()).days
    
    # Debug: log what we're calculating
    print(f"DEBUG: Surgery='{surgery_date_str}' -> {surgery_date.date()}, Today={now.date()}, days_until={days_until_surgery}, weeks_post={weeks}")
    
    if days_until_surgery > 0:
        weeks_until = max(1, math.ceil(days_until_surgery / 7))
        return f"PRE-OP (Surgery in {weeks_until} weeks)"
    elif weeks == 0:
        return "PHASE 1: Clear Liquids (Week 1)"
    elif weeks == 1:
        return "PHASE 2: Full Liquids (Week 2)"
    elif 2 <= weeks < 4:
        return f"PHASE 3: Pureed/Soft Foods (Week {weeks+1})"
    elif 4 <= weeks < 8:
        return f"PHASE 4: Adaptive/Regular Soft Diet (Week {weeks+1})"
    else:
        return f"PHASE 5: Solid Foods / Maintenance (Week {weeks+1})"

async def generate_and_persist_memory(user_id: str, prev_memory: str, last_message: str, assistant_response: str):
    """Background task to generate updated memory."""
    if not user_id:
        return
    try:
        memory_prompt = (
            f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.\n"
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

        # Extract digits from user_id for Storage API
        m = re.search(r'\d+', str(user_id))
        if m:
            user_id_int = int(m.group())
        else:
            try:
                user_id_int = int(user_id)
            except ValueError:
                user_id_int = 1  # Fallback for sweep test cases
                
        # Save to Storage Service
        async with httpx.AsyncClient() as client:
            await client.put(f"{STORAGE_URL}/me/{user_id_int}/memory", json={"memory": new_memory})
        
    except Exception as e:
        print(f"ERROR: Memory update failed: {e}")

# ==========================================
# 4. AGENTS
# ==========================================

# 4.1 PREPROCESSOR
async def preprocessor_agent(state: MultiAgentState) -> dict:
    """Preprocesses user input (currently pass-through)."""
    # Could expand shorthand replies here in the future
    return {}

# 4.2 RESEARCHER (RAG)
async def research_agent(state: MultiAgentState) -> dict:
    """Queries Knowledge Base for clinical facts."""
    messages = state.get("messages", [])
    if not messages:
        return {"clinical_context": ""}
        
    last_message = messages[-1].content
    low = last_message.lower().strip()
    # Skip casual or short queries to save latency
    skip_prefixes = ["hi", "hello", "thanks", "thank you", "bye"]
    if len(last_message) < 12 or any(low.startswith(p) for p in skip_prefixes):
        return {"clinical_context": ""}
        
    print(f"--- RESEARCHER: Searching knowledge for '{last_message}' ---")
    context = query_knowledge(last_message, n_results=RAG_RESULTS)
    
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

    is_profile_request = any(k in low for k in ["my profile", "my stats", "surgery date", "allergies"])
    
    # 1. Logging (LLM-classified for consistency)
    if user_id:
        skip_prefixes = ["hi", "hello", "thanks", "thank you", "bye"]
        if len(low) > 6 and not any(low.startswith(p) for p in skip_prefixes):
            # Only use user-provided macros (avoid hallucinated numbers)
            m_user_prot = re.search(r'(\d+(?:\.\d+)?)\s*(g|grams)?\s*protein', low)
            m_user_cal = re.search(r'(\d+(?:\.\d+)?)\s*(kcal|calories|calorie)', low)
            user_protein = float(m_user_prot.group(1)) if m_user_prot else 0.0
            user_calories = float(m_user_cal.group(1)) if m_user_cal else 0.0

            # Build conversation history for context (last 4 messages)
            conversation_context = ""
            if len(messages) > 1:
                recent_msgs = messages[-5:-1] if len(messages) >= 5 else messages[:-1]
                context_lines = []
                for msg in recent_msgs:
                    if isinstance(msg, HumanMessage):
                        context_lines.append(f"User: {msg.content}")
                    elif isinstance(msg, AIMessage):
                        context_lines.append(f"Assistant: {msg.content[:150]}")  # Truncate long responses
                conversation_context = "\n".join(context_lines[-4:])  # Keep last 4 exchanges

            nutrition_prompt = f"""
            Today is {datetime.now().strftime('%A, %B %d, %Y')}.
            
            Decide if the user is reporting a meal they ALREADY ate today.
            If they are asking a hypothetical question (e.g., "Can I have...", "What if..."), answer NO.
            If they ALREADY ate it, extract a summarized food name and estimate protein/calories
            using realistic single-serving portions (do not exaggerate).
            
            IMPORTANT: If the user says "record that", "log that", "log it", or similar references,
            check the CONVERSATION HISTORY below to find what food was just discussed.
            
            For MEAL: Use the specific food name mentioned (e.g., "Greek yogurt", "Grilled chicken breast", "Protein shake").
            For PROTEIN and CALORIES: Provide realistic estimates based on typical serving sizes.
            
            Respond in this exact format:
            MEAL_LOG: YES|NO
            MEAL: [food name]
            PROTEIN: [realistic grams or 0]
            CALORIES: [realistic kcal or 0]

            CONVERSATION HISTORY:
            {conversation_context if conversation_context else "(No previous conversation)"}

            Current User Message: "{last_message}"
            """
            try:
                resp = await llm.ainvoke([HumanMessage(content=nutrition_prompt)])
                text = resp.content.strip()
                m_log = re.search(r'MEAL_LOG:\s*(YES|NO)', text, re.IGNORECASE)
                m_meal = re.search(r'MEAL:\s*(.*?)(?:\n|$)', text)  # Capture until newline
                m_prot = re.search(r'PROTEIN:\s*(\d+(?:\.\d+)?)', text)
                m_cal = re.search(r'CALORIES:\s*(\d+(?:\.\d+)?)', text)

                is_meal_log = bool(m_log and m_log.group(1).upper() == "YES")
                meal_name = m_meal.group(1).strip() if m_meal else ""
                has_log_intent = bool(re.search(
                    r"\b(record|log|track|add)\b|\b(i just ate|i ate|i had|i've eaten|i've had|i have eaten)\b",
                    low,
                    re.IGNORECASE
                ))
                
                # Clean up meal name from LLM (remove quotes, brackets, etc.)
                if meal_name:
                    meal_name = meal_name.strip('"\'[]')
                    if meal_name and not meal_name[0].isupper():  # Capitalize if not already
                        meal_name = meal_name.capitalize()

                # Guard against placeholder/non-food outputs
                invalid_meal_markers = [
                    "no specific food",
                    "cannot determine meal",
                    "unknown",
                    "not provided",
                    "n/a",
                ]
                if meal_name and any(marker in meal_name.lower() for marker in invalid_meal_markers):
                    meal_name = ""

                # Fallback: derive meal name from user message or conversation history if LLM format is incomplete
                reference_words = ["that", "it", "this", "the meal", "the food", "same thing"]
                is_reference = any(ref in low for ref in reference_words) and ("record" in low or "log" in low)
                
                if not meal_name and is_meal_log:
                    # First try: extract from current message
                    cleaned = re.sub(r"^(i just ate|i ate|i had|log|i have eaten|i've eaten|i've had|i ate a|i had a|record that i have eaten|record that i ate|just ate|just had|record that|log that|record it|log it)\s+", "", low, flags=re.IGNORECASE)
                    meal_name = cleaned.strip().title() if cleaned.strip() else ""
                    
                    # Second try: If user is referencing something, look in conversation history
                    if is_reference and (not meal_name or meal_name in ["That", "It", "This", "what you said"]) and len(messages) > 1:
                        # Look for food mentions in recent assistant responses
                        for msg in reversed(messages[-4:-1]):  # Check last 3 messages before current
                            if isinstance(msg, AIMessage):
                                content_lower = msg.content.lower()
                                # Look for food-related patterns in assistant's response
                                food_patterns = [
                                    r'(?:try|have|eat|recommend|suggest|good choice|great option)\s+(?:some\s+)?([a-z\s]+?)(?:\.|,|\?|!|\n)',
                                    r'(?:like|such as)\s+([a-z\s]+?)(?:\.|,|or|\n)',
                                ]
                                for pattern in food_patterns:
                                    match = re.search(pattern, content_lower)
                                    if match:
                                        potential_food = match.group(1).strip()
                                        if len(potential_food) > 3 and len(potential_food) < 50:  # Reasonable food name length
                                            meal_name = potential_food.title()
                                            break
                            if meal_name and meal_name not in ["That", "It", "This"]:
                                break

                estimated_protein = float(m_prot.group(1)) if m_prot else 0.0
                estimated_calories = float(m_cal.group(1)) if m_cal else 0.0

                # Use user-provided macros when available, otherwise use estimates
                protein_grams = user_protein if user_protein > 0 else estimated_protein
                calories = user_calories if user_calories > 0 else estimated_calories

                # Fill in missing macros with conservative estimates based on the other value
                if protein_grams <= 0 and calories > 0:
                    # Estimate protein from calories (~20-25% of calories from protein)
                    protein_grams = round(max(5.0, min(calories / 18.0, 40.0)), 1)
                if calories <= 0 and protein_grams > 0:
                    # Estimate calories from protein (protein = 4 cal/g, plus some fat/carbs)
                    calories = round(max(100.0, min(protein_grams * 10.0, 600.0)), 0)
                if protein_grams <= 0 and calories <= 0:
                    # Conservative defaults for unknown meal
                    protein_grams = 12.0
                    calories = 200.0

                # Clamp to reasonable single-meal ranges for bariatric patients
                protein_grams = round(min(max(protein_grams, 0.0), 60.0), 1)
                calories = round(min(max(calories, 0.0), 900.0), 0)

                if is_meal_log and meal_name and has_log_intent:
                    # Avoid duplicate consecutive logs of the same meal with same macros
                    todays_meals = profile.get("todays_meals", []) if isinstance(profile, dict) else []
                    if todays_meals:
                        last_logged = todays_meals[-1]
                        last_food = str(last_logged.get("food", "")).strip().lower()
                        last_protein = float(last_logged.get("protein", 0) or 0)
                        last_calories = float(last_logged.get("calories", 0) or 0)
                        same_meal = last_food == meal_name.strip().lower()
                        same_macros = abs(last_protein - protein_grams) <= 0.1 and abs(last_calories - calories) <= 1.0
                        if same_meal and same_macros:
                            data_response = f"ACTION_SKIPPED: '{meal_name}' is already logged for today."
                            return {"data_response": data_response}

                    result = await record_meal.ainvoke({
                        "user_id": user_id,
                        "meal_name": meal_name,
                        "protein_grams": protein_grams,
                        "calories": calories
                    })
                    if result.get("success"):
                        if user_protein > 0:
                            protein_note = f"{user_protein}g"
                        elif protein_grams > 0:
                            protein_note = f"estimated {protein_grams}g"
                        else:
                            protein_note = "not provided"

                        if user_calories > 0:
                            calories_note = f"{user_calories} kcal"
                        elif calories > 0:
                            calories_note = f"estimated {calories} kcal"
                        else:
                            calories_note = "not provided"
                        data_response = (
                            f"ACTION_TAKEN: Logged {meal_name}. "
                            f"Protein: {protein_note}. Calories: {calories_note}. "
                            f"Daily Total: {result.get('protein_total')}g protein."
                        )
                    else:
                        data_response = f"ACTION_FAILED: {result.get('error')}"
            except Exception as e:
                data_response = f"ACTION_FAILED: Classification error {e}"

    # 2. Data Context (Always provide if available)
    # Skip context if a meal was just logged - keep response simple
    if data_response.startswith("ACTION_TAKEN:") or data_response.startswith("ACTION_FAILED:") or data_response.startswith("ACTION_SKIPPED:"):
        return {"data_response": data_response}
    
    parts = []
    if profile:
        surg_date = profile.get('surgery_date', 'N/A')
        parts.append(f"Surgery Date: {surg_date}")
        if surg_date != 'N/A' and surg_date:
            phase = _calculate_post_op_phase(surg_date)
            parts.append(f"Current Phase: {phase}")
        parts.append(f"Diet: {profile.get('diet_type', 'N/A')}")
        parts.append(f"Activity Level: {profile.get('activity_level', 'N/A')}")
        if profile.get('allergies'):
            parts.append(f"Allergies: {', '.join(profile.get('allergies'))}")
        if profile.get('disliked_foods'):
            parts.append(f"Disliked Foods: {', '.join(profile.get('disliked_foods'))}")
    
    if is_profile_request:
        data_response = (data_response + "\n" if data_response else "") + "PATIENT_FILE_REQUESTED:\n" + "\n".join(parts)
    elif parts and not data_response:
        data_response = "PATIENT_CONTEXT:\n" + "\n".join(parts)
        
    return {"data_response": data_response}

# 4.4 DIETITIAN (NUTRITION LOOKUP)
async def dietitian_agent(state: MultiAgentState) -> dict:
    """Queries OpenFoodFacts API for specific foods mentioned."""
    messages = state.get("messages", [])
    if not messages:
        return {"nutrition_context": ""}
        
    last_message = messages[-1].content
    low = last_message.lower().strip()
    
    # Simple trigger keywords indicating the user is asking about nutrition facts
    nutrition_keywords = ["protein in", "calories in", "macros", "how many calories", "how much protein", "nutrition facts", "how much fat", "carbs in", "serving size"]
    is_asking_nutrition = any(k in low for k in nutrition_keywords)
    
    # If not asking for nutrition facts, but asking for meal ideas, we don't need to look up a specific food yet.
    if not is_asking_nutrition:
        return {"nutrition_context": ""}
        
    print(f"--- DIETITIAN: Checking nutrition for '{last_message}' ---")
    
    prompt = f"""
    Extract the main single food item the user is asking about in this message.
    Return ONLY the raw food name (e.g. "eggs", "chicken breast", "broccoli", "edamame") with NO punctuation, NO quantities, and NO extra text.
    If multiple foods, pick the primary one.
    User message: "{last_message}"
    """
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        food_query = resp.content.strip().replace('"', '')
        
        if food_query:
            nutrition_data = await search_nutrition.ainvoke({"food_query": food_query})
            if "error" not in nutrition_data:
                context = (
                    f"Food: {nutrition_data['food_name']}\n"
                    f"Serving Size: {nutrition_data['serving_size']}\n"
                    f"Calories: {nutrition_data['calories']} kcal\n"
                    f"Protein: {nutrition_data['protein_g']}g\n"
                    f"Carbs: {nutrition_data['carbs_g']}g\n"
                    f"Fat: {nutrition_data['fat_g']}g"
                )
                print(f"--- DIETITIAN: Found data for {food_query} ---")
                return {"nutrition_context": context}
            else:
                print(f"--- DIETITIAN: No data found ({nutrition_data['error']}) ---")
    except Exception as e:
        print(f"--- DIETITIAN Error: {e} ---")
        
    return {"nutrition_context": ""}

# 4.5 SYNTHESIS (DOCTOR)
async def assistant_agent(state: MultiAgentState) -> dict:
    """Synthesizes final response using Research + Nurse + Dietitian Data."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    low_message = last_message.lower().strip()
    profile = state.get("profile") or {}
    convo_excerpt = state.get("conversation_log") or "[]"
    
    clinical_context = state.get("clinical_context") or ""
    data_response = state.get("data_response") or ""
    nutrition_context = state.get("nutrition_context") or ""
    
    # Prompt Construction - Add contextual data to help the LLM respond
    parts = []
    recent_recommendations = []
    
    # Add current date so LLM knows what day it is
    current_date = datetime.now().strftime("%A, %B %d, %Y")
    parts.append(f"[CONTEXT] Today's date: {current_date}")
    
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

    if include_todays_meals and convo_excerpt and convo_excerpt != "[]":
        try:
            convo = json.loads(convo_excerpt)
            recent_assistant = list(convo.get("recent_assistant_responses", []))
            recent_recommendations = [msg for msg in recent_assistant[-3:] if isinstance(msg, str) and msg.strip()]
        except Exception:
            recent_recommendations = []
    
    recently_suggested_ingredients = set()
    if recent_recommendations:
        for rec in recent_recommendations:
            keywords = re.findall(r'\b(chicken|salmon|tilapia|cod|turkey|beef|tofu|eggs?|greek yogurt|yogurt|broccoli|spinach|kale|asparagus|carrots?|zucchini|lettuce|beans?|lentils|rice|quinoa)\b', rec.lower())
            recently_suggested_ingredients.update(keywords)

    todays_meals = profile.get("todays_meals") or []
    if include_todays_meals and todays_meals:
        meal_names = []
        primary_ingredients = set()
        for meal in todays_meals:
            meal_str = ""
            if isinstance(meal, dict) and meal.get("food"):
                meal_str = str(meal.get("food"))
            elif isinstance(meal, str):
                meal_str = meal
            if meal_str:
                meal_names.append(meal_str)
                # Extract key ingredients (proteins/vegetables mentioned in the meal name)
                keywords = re.findall(r'\b(chicken|salmon|tilapia|cod|turkey|beef|tofu|eggs?|greek yogurt|yogurt|broccoli|spinach|kale|asparagus|carrots?|zucchini|lettuce|beans?|lentils|rice|quinoa)\b', meal_str.lower())
                primary_ingredients.update(keywords)
        if meal_names:
            meal_context = "[TODAYS_MEALS]\n" + "\n".join(meal_names[:20])
            if primary_ingredients:
                meal_context += f"\n[PRIMARY_INGREDIENTS_TO_AVOID_REPEATING]\n" + ", ".join(sorted(primary_ingredients))
            parts.append(meal_context)
    if recent_recommendations:
        rec_context = "[RECENT_RECOMMENDATIONS]\n" + "\n---\n".join(recent_recommendations)
        if recently_suggested_ingredients:
            rec_context += f"\n[RECENTLY_SUGGESTED_INGREDIENTS_AVOID]\n" + ", ".join(sorted(recently_suggested_ingredients))
        parts.append(rec_context)
    if data_response:
        parts.append(f"[DATA]\n{data_response}\n[DATA_RULE]\nUse DATA only if directly relevant to the current question.")
    if nutrition_context:
        parts.append(f"[OPEN_FOOD_FACTS_NUTRITION]\n{nutrition_context}\n[NUTRITION_RULE]\nIncorporate these exact macros into your response.")
    
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
            
            # Strip thought blocks if they exist
            if "<thought>" in final_response:
                final_response = re.sub(r"<thought>.*?</thought>\s*", "", final_response, flags=re.DOTALL).strip()
                # If model forgot closing tag, strip the opening tag at least
                final_response = final_response.replace("<thought>", "").strip()
                
        except Exception as e:
            print(f"LLM INVOCATION ERROR: {e}")
            final_response = "I'm having trouble thinking right now. Please try again."

    # Don't add separate confirmation for meal logging - let AI handle it from data_response

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
workflow.add_node("preprocessor", preprocessor_agent)
workflow.add_node("researcher", research_agent)
workflow.add_node("nurse", patient_data_agent)
workflow.add_node("dietitian", dietitian_agent)
workflow.add_node("assistant", assistant_agent)

workflow.set_entry_point("preprocessor")
workflow.add_edge("preprocessor", "researcher")
workflow.add_edge("researcher", "nurse")
workflow.add_edge("nurse", "dietitian")
workflow.add_edge("dietitian", "assistant")
workflow.add_edge("assistant", END)

app = workflow.compile()
print("Sequential Agent System Compiled!")
