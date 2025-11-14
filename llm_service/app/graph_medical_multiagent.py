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
    conversation_log: Optional[str]
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

# ------------------------------------------
# 2.5 PREPROCESSOR: handle shorthand replies
# ------------------------------------------
async def preprocessor_agent(state: MultiAgentState) -> dict:
    """
    Detect short/shorthand user replies ("yes", "no", "the first option", "1", "that one")
    and expand them into a full-text user message that includes the last assistant
    question from the `conversation_log`. This helps downstream agents interpret
    ambiguous replies without getting confused.
    """
    try:
        messages = state.get("messages", [])
        if not messages:
            return {"messages": messages}

        last_user = messages[-1].content.strip()
        # Heuristic: treat very short replies or ordinal/numeric responses as shorthand
        tokens = last_user.lower().split()
        shorthand_triggers = {"yes", "no", "y", "n", "yeah", "yep", "nope", "ok", "okay", "first", "second", "third", "1", "2", "3", "the first", "the second", "the third", "that one", "that", "this one", "option 1", "option 2", "option 3"}

        is_shorthand = len(tokens) <= 3 or any(t in shorthand_triggers for t in tokens)

        if not is_shorthand:
            return {"messages": messages}

        # Get last assistant text from conversation_log if available (prefer question, else fallback to last response)
        convo = state.get("conversation_log") or "[]"
        assistant_text = None
        try:
            import json as _json
            parsed = _json.loads(convo) if isinstance(convo, str) else convo
            # New format: dict with recent_assistant_responses
            if isinstance(parsed, dict):
                recent_assist = parsed.get("recent_assistant_responses", []) or []
                if recent_assist:
                    # prefer last entry that looks like a question
                    for txt in reversed(recent_assist):
                        if isinstance(txt, str) and txt.strip().endswith("?"):
                            assistant_text = txt
                            break
                    if assistant_text is None:
                        assistant_text = recent_assist[-1]
            elif isinstance(parsed, list):
                # legacy list of role-tagged entries
                for entry in reversed(parsed):
                    if isinstance(entry, dict) and entry.get("role") == "assistant":
                        if entry.get("is_question"):
                            assistant_text = entry.get("text")
                            break
                        if isinstance(entry.get("text"), str) and entry.get("text").strip().endswith("?"):
                            assistant_text = entry.get("text")
                            break
                if assistant_text is None:
                    # fallback to last assistant entry text
                    for entry in reversed(parsed):
                        if isinstance(entry, dict) and entry.get("role") == "assistant":
                            assistant_text = entry.get("text")
                            break
            # If still not found, try to use last assistant message from in-memory messages
            if assistant_text is None:
                for m in reversed(messages[:-1]):
                    try:
                        if m.__class__.__name__ == 'AIMessage' or getattr(m, 'type', None) == 'ai':
                            txt = getattr(m, 'content', None)
                            if isinstance(txt, str) and txt.strip():
                                assistant_text = txt
                                break
                    except Exception:
                        continue
        except Exception:
            assistant_text = None

        # Try to parse enumerated options and map ordinals (including inline lists and forms like '2nd', 'option two')
        expanded = None
        try:
            if assistant_text:
                aq = assistant_text
                import re
                opts = []
                # 1) Lines starting with numbered or lettered bullets: '1) option' or 'a) option'
                for line in aq.splitlines():
                    m = re.match(r"\s*(?:[0-9]+|[a-zA-Z])\s*[\).:-]\s*(.+)", line)
                    if m:
                        opts.append(m.group(1).strip())
                # 2) Bullet lines starting with '-' or '•'
                if not opts:
                    for line in aq.splitlines():
                        m = re.match(r"\s*[-•]\s*(.+)", line)
                        if m:
                            opts.append(m.group(1).strip())
                # 3) Inline 'Options: x, y, z' or 'Choose: x, y, z'
                if not opts:
                    inline_match = re.search(r"(?:options?|choose(?: from)?|choices?)[:\-]\s*(.+)", aq, flags=re.IGNORECASE)
                    if inline_match:
                        tail = inline_match.group(1)
                        parts = [p.strip() for p in re.split(r",|/|;|\\n", tail) if p.strip()]
                        opts.extend(parts)
                # 4) Fallback: split long comma-separated lines if they look like a list
                if not opts:
                    for line in aq.splitlines():
                        if ',' in line and len(line) < 200:
                            parts = [p.strip() for p in line.split(',') if p.strip()]
                            if len(parts) >= 2:
                                opts.extend(parts)

                # Map shorthand tokens to indexes (include '1st','2nd','3rd')
                ordinal_map = {
                    'first': 0, '1': 0, 'one': 0, '1st': 0,
                    'second': 1, '2': 1, 'two': 1, '2nd': 1,
                    'third': 2, '3': 2, 'three': 2, '3rd': 2,
                    'fourth': 3, '4': 3, 'four': 3, '4th': 3
                }

                chosen_text = None
                # Prefer explicit numeric/ordinal tokens found in the user's reply
                for t in tokens:
                    if t in ordinal_map and opts:
                        idx = ordinal_map[t]
                        if idx < len(opts):
                            chosen_text = opts[idx]
                            break

                # Also match patterns like 'option 2' or 'choose 2' in the user's reply
                if not chosen_text:
                    mnum = re.search(r"option[s]?\s*(?:number)?\s*(\d+)", last_user, flags=re.IGNORECASE)
                    if mnum and opts:
                        idx = int(mnum.group(1)) - 1
                        if 0 <= idx < len(opts):
                            chosen_text = opts[idx]

                # If user used words like 'that one' without explicit ordinal, leave ambiguous and fallback later
                if chosen_text:
                    expanded = f"User selected option referring to: '{chosen_text}' (original reply: '{last_user}')"
        except Exception:
            expanded = None

                # Default expansion if no enumerated mapping was possible
        if expanded is None:
            # Use the assistant_text we extracted earlier (may be None)
            if assistant_text:
                expanded = f"User replied '{last_user}' in response to the assistant question: '{assistant_text}'"
            else:
                expanded = f"User replied '{last_user}' (context: previous assistant question not found)"

        # Replace the last message with the expanded content
        from langchain_core.messages import HumanMessage as _HM
        messages[-1] = _HM(content=expanded)
        return {"messages": messages}

    except Exception as e:
        print(f"--- PREPROCESSOR: error expanding shorthand reply: {e} ---")
        return {"messages": state.get("messages", [])}


async def assistant_agent(state: MultiAgentState) -> dict:
    """
    Simplified single assistant that handles optional data fetching,
    produces concise medical guidance + example meals, enforces
    deterministic allergy/dislike filtering, emits an context-aware
    follow-up, and returns an updated structured memory JSON.
    """
    print("--- ASSISTANT AGENT: Processing query ---")

    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    profile = state.get("profile") or {}
    prev_memory = state.get("memory") or ""
    convo_excerpt = state.get("conversation_log") or "[]"
    patient_id = state.get("patient_id")
    # Control flags
    early_response = None
    no_closing_question = False

    # Helper: small wrapper to make LLM calls more conversational and bias recency
    async def _llm_invoke(text: str):
        suffix = (
            "\n\nBe conversational and friendly. Keep answers concise and helpful. "
            "End your answer with a short question like 'How else can I help?'"
        )
        try:
            return await llm.ainvoke([HumanMessage(content=text + suffix)])
        except Exception:
            # Fallback to a plain invoke if wrapper fails
            return await llm.ainvoke([HumanMessage(content=text)])

    # Build a recent-focused conversation excerpt (most recent first) to bias
    # the LLM toward the latest context. This is a compact string used in prompts.
    def _build_recent_excerpt(convo: str) -> str:
        try:
            parsed = json.loads(convo) if isinstance(convo, str) else (convo or {})
            if isinstance(parsed, dict):
                recent_user = parsed.get("recent_user_prompts", []) or []
                recent_assistant = parsed.get("recent_assistant_responses", []) or []
            elif isinstance(parsed, list):
                recent_user = [e.get("text") for e in parsed if isinstance(e, dict) and e.get("role") == "user"]
                recent_assistant = [e.get("text") for e in parsed if isinstance(e, dict) and e.get("role") == "assistant"]
            else:
                recent_user = []
                recent_assistant = []
        except Exception:
            recent_user = []
            recent_assistant = []

        # Limit and order most recent first for recency bias
        ru = list(recent_user[-5:])[::-1]
        ra = list(recent_assistant[-5:])[::-1]

        ra_str = "\n".join([f"- {r}" for r in ra]) if ra else "(none)"
        ru_str = "\n".join([f"- {r}" for r in ru]) if ru else "(none)"
        return (
            "Recent assistant responses (most recent first):\n" + ra_str +
            "\n\nRecent user prompts (most recent first):\n" + ru_str
        )

    convo_recent_str = _build_recent_excerpt(convo_excerpt)

    # Optional patient data fetch
    data_resp = None
    if ENABLE_PATIENT_TOOLS and patient_id:
        try:
            pdata = await get_patient_data.ainvoke({"patient_id": patient_id})
            if isinstance(pdata, dict) and "error" not in pdata:
                data_resp = f"Patient Data Retrieved:\n{json.dumps(pdata, indent=2)}"
            else:
                err = pdata.get("error") if isinstance(pdata, dict) else str(pdata)
                data_resp = f"Note: I couldn't access patient-specific data. Details: {err}"
        except Exception as e:
            data_resp = f"Error fetching patient data: {e}"
    else:
        data_resp = "Note: patient tools disabled or no patient_id provided. Responding generally."

    # intent detection (grocery, calorie, recipe, profile, meal, general)
    low = last_message.lower()
    is_grocery = any(k in low for k in ["grocery", "shopping list", "shopping", "grocery list"]) or "grocery" in low
    is_calorie = any(k in low for k in ["calorie", "calories", "calorie breakdown"]) or "calorie" in low
    is_recipe = any(k in low for k in ["recipe", "how to make", "how do i make", "cook", "instructions"]) or "recipe" in low
    is_profile = any(k in low for k in ["what are my food preferences", "my profile", "what is my profile", "what are my allergies", "do i have any allergies"]) 
    wants_meals = any(k in low for k in ["meal", "meals", "lunch", "dinner", "breakfast", "meal ideas", "suggest" ,"suggestions"]) and not is_grocery and not is_recipe

    # Politeness and conversational cues
    greetings = ("hi", "hello", "hey", "good morning", "good afternoon", "good evening")
    thanks_words = ("thank", "thanks", "thank you", "thx", "ty")
    goodbyes = ("bye", "goodbye", "see you", "see ya", "talk later", "later", "take care")

    is_greeting = any(low.strip().startswith(g) for g in greetings)
    is_thanks = any(g in low for g in thanks_words)
    is_goodbye = any(g in low for g in goodbyes)

    # If greeting, respond with a friendly greeting. Do NOT clear the stored
    # conversation excerpt (preserve history). Only treat short messages as
    # greetings so longer inputs like "hello I have a question about X" still
    # run through the normal flow.
    tokens = low.split()
    if is_greeting and len(tokens) <= 4:
        early_response = "Hello! I'm your bariatric surgery assistant. How can I help you today?"

    # If the user says goodbye, reply politely and don't append the usual closing question.
    if is_goodbye and len(tokens) <= 6:
        early_response = "Goodbye — wishing you a smooth recovery and good health. Take care!"
        no_closing_question = True

    # If the user thanks the assistant, show manners and offer any further help.
    if is_thanks and len(tokens) <= 6:
        early_response = "You're welcome! I'm glad I could help. Is there anything else I can do for you?"

    # helper to fetch last assistant text from conversation_log or messages
    def _get_recent_assistant_text():
        # prefer conversation_log entries
        try:
            parsed = json.loads(convo_excerpt) if isinstance(convo_excerpt, str) else convo_excerpt
            if isinstance(parsed, dict):
                recent = parsed.get("recent_assistant_responses", []) or []
                if recent:
                    return recent[-1]
            elif isinstance(parsed, list):
                for entry in reversed(parsed):
                    if isinstance(entry, dict) and entry.get("role") == "assistant":
                        txt = entry.get("text") or entry.get("content")
                        if isinstance(txt, str) and txt.strip():
                            return txt
        except Exception:
            pass
        # fallback to messages
        for m in reversed(messages[:-0]):
            try:
                if getattr(m, '__class__', None).__name__ == 'AIMessage' or getattr(m, 'type', None) == 'ai':
                    txt = getattr(m, 'content', None)
                    if isinstance(txt, str) and txt.strip():
                        return txt
            except Exception:
                continue
        return None

    recent_assistant = _get_recent_assistant_text()

    # Topicality check: only mark off-topic when there are clear indicators
    # that the user is asking about unrelated domains (finance, sports,
    # entertainment, politics, etc.). Default to permissive (on-topic) so the
    # redirect is rare and only used when the conversation is clearly off-track.
    def _is_on_topic(msg: str) -> bool:
        if not msg:
            return True
        low = msg.lower()
        # Allow brief greetings and polite phrases
        smalltalk = ("hi", "hello", "hey", "thanks", "thank", "bye", "goodbye", "good morning", "good evening")
        if any(low.startswith(s) for s in smalltalk):
            return True

        # Keywords indicating bariatric/post-op/nutrition topics — if present,
        # definitely treat as on-topic.
        topic_keywords = [
            "bariatric", "surgery", "post-op", "post op", "postop", "weight loss",
            "gastric", "sleeve", "bypass", "revision", "nutrition", "protein",
            "calorie", "meal", "diet", "allergy", "allergies", "dislike", "exercise",
            "activity", "recovery", "complication", "vomit", "nausea", "food",
            "incision", "wound", "suture", "breakfast", "follow up", "lunch", "dinner",
        ]
        if any(k in low for k in topic_keywords):
            return True

        # Explicit off-topic domains that should trigger the redirect only when
        # there is no overlap with topic keywords. These are things like
        # finance, sports, politics, entertainment, and other unrelated areas.
        off_topic_keywords = [
            "finance", "money", "bank", "loan", "mortgage", "rent", "salary", "stocks", "invest", "investment",
            "sports", "football", "soccer", "basketball", "baseball", "nba", "nfl", "mlb", "cricket",
            "movie", "movies", "tv", "show", "celebrity", "music", "concert", "gaming", "video game",
            "politics", "election", "government", "policy", "religion", "prayer",
            "dating", "relationship advice" , "gambling"
        ]
        if any(k in low for k in off_topic_keywords):
            return False

        # Short context-dependent replies should be allowed so the preprocessor
        # can expand them using conversation_log.
        if low.strip() in {"yes", "no", "y", "n", "okay", "ok"}:
            return True

        # Default: be permissive and treat as on-topic (avoids false positives).
        return True

    off_topic = not _is_on_topic(last_message)
    # If an early deterministic response exists (greeting/thanks/goodbye), keep it aside
    # but still run the main LLM/tool flow so tool access is preserved. We'll prefer
    # the early deterministic response only after the LLM flow completes successfully
    # for truly pure greetings/thanks/goodbyes.
    chosen_early = early_response

    # Handle specialized intents first (grocery, calorie, recipe, profile)
    if off_topic:
        # Polite redirect when user drifts away from bariatric/post-op help
        final_response = (
            "I can only help with bariatric surgery and related post-operative care. "
            "If you have questions about recovery, diet, meals, activity, or surgery-specific concerns, "
            "please ask and I will do my best to help. For other topics, I am not able to assist."
        )
    elif is_grocery:
        # Produce a consolidated grocery list based on the most recent assistant meal suggestions
        if recent_assistant:
            prompt = f"""
You are a helpful assistant that turns meal suggestions into a consolidated grocery shopping list grouped by typical grocery sections (produce, dairy, proteins, pantry, spices, frozen).\n\nMeal suggestions (most recent first):\n{convo_recent_str}\n\nReturn a short, deduplicated shopping list with approximate quantities where reasonable.
"""
            resp = await _llm_invoke(prompt)
            final_response = resp.content.strip()
        else:
            final_response = "I couldn't find recent meal suggestions to build a grocery list from. Could you tell me which meals you want a shopping list for?"

    elif is_calorie:
        if recent_assistant:
            prompt = f"""
Given the following meal suggestions, produce a concise calorie estimate per meal and per serving, and a brief note on how to reduce calories if needed:\n\n{convo_recent_str}\n\nFormat as bullets: Meal name - estimated calories per serving (short note)."""
            resp = await _llm_invoke(prompt)
            final_response = resp.content.strip()
        else:
            final_response = "I couldn't find recent meals to break down. Which meal would you like a calorie estimate for?"

    elif is_recipe:
        # try to extract meal name from user's request
        import re
        m = re.search(r"for\s+([\w\s'-]+)$", last_message, re.IGNORECASE)
        target = None
        if m:
            target = m.group(1).strip()
        if not target and recent_assistant:
            # try to pick the first meal name from recent assistant text (looks for lines starting with a name)
            lines = recent_assistant.splitlines()
            if lines:
                target = lines[0].strip()
        if target:
            prompt = f"""
Provide step-by-step recipe instructions suitable for a post-bariatric patient for the dish: {target}. Keep steps simple, focus on protein, soft textures if early post-op, and include approximate times and an easy serving size."""
            resp = await _llm_invoke(prompt)
            final_response = resp.content.strip()
        else:
            final_response = "Which recipe would you like instructions for?"

    elif is_profile:
        if profile:
            disliked = profile.get("disliked_foods") or []
            allergies = profile.get("allergies") or []
            diet_type = profile.get("diet_type") or "not specified"
            surgery_date = profile.get("surgery_date") or "not specified"
            parts = [f"Diet type: {diet_type}."]
            parts.append(f"Disliked foods: {', '.join(disliked) if disliked else 'none recorded'}.")
            parts.append(f"Allergies/intolerances: {', '.join(allergies) if allergies else 'none recorded'}.")
            parts.append(f"Surgery date: {surgery_date}.")
            final_response = " ".join(parts) + "\n\n(You can edit these in Settings → Edit Profile.)"
        else:
            final_response = "I don't have your profile data yet. You can set dislikes, allergies, diet type, and surgery date in Settings → Edit Profile."

    else:
        # General case: if user asked for meals explicitly, produce meal suggestions; otherwise produce general medical guidance and optionally brief actionable tips
        if wants_meals:
            prompt = f"""
You are a helpful medical assistant. Produce three example meals (Breakfast, Lunch, Dinner) tailored to the user's profile when present. For each meal include a one-line description, approximate serving size, and an estimated calorie range (e.g., 250-400 kcal). Keep it concise and skimmable.\n\nContext:\nUser question: '{last_message}'\nProfile: {json.dumps(profile)}\nPrevious memory: {prev_memory}\nRecent conversation excerpt: {convo_recent_str}\n"""
            resp = await _llm_invoke(prompt)
            final_response = resp.content.strip()
        else:
            # Produce concise medical guidance + 1-2 short applicable tips (not always meals)
            prompt = f"""
You are a concise medical assistant specializing in bariatric post-op care. Answer the user's question in 2-4 sentences and include 1-2 short actionable tips (behavioral, dietary, or activity) relevant to the query. Do NOT produce meal examples unless the user asks for them.\n\nUser question: '{last_message}'\nProfile: {json.dumps(profile)}\nPrevious memory: {prev_memory}\nRecent conversation excerpt: {convo_recent_str}\n"""
            resp = await _llm_invoke(prompt)
            final_response = resp.content.strip()

    # Append a context-aware follow-up (reuse the helper defined earlier if present)
    try:
        follow_up = _choose_follow_up(final_response) if '_choose_follow_up' in globals() or '_choose_follow_up' in locals() else None
        if follow_up:
            final_response = final_response + "\n\n" + follow_up
    except Exception:
        pass

    print("--- ASSISTANT: Primary response created ---")

    # If an early deterministic response was set (greeting/thanks/goodbye),
    # prefer it only when the LLM produced an equally short/generic reply or
    # nothing. This allows tools and LLM flow to run (so tool access isn't
    # lost) but still returns a polite deterministic reply for pure greetings.
    try:
        if early_response:
            low_final = (final_response or "").lower()
            greeting_like = any(p in low_final for p in ["hello", "hi", "goodbye", "you're welcome", "thanks"]) or len(low_final.strip()) < 20
            if not final_response or greeting_like:
                final_response = early_response
    except Exception:
        pass

    # Deterministic allergy/disliked-foods filter (line-level removal)
    try:
        forbidden = set()
        profile_allergies = profile.get("allergies") if isinstance(profile, dict) else []
        profile_disliked = profile.get("disliked_foods") if isinstance(profile, dict) else []
        for a in (profile_allergies or []):
            if isinstance(a, str) and a.strip():
                forbidden.add(a.lower())
        for d in (profile_disliked or []):
            if isinstance(d, str) and d.strip():
                forbidden.add(d.lower())

        if forbidden:
            import re
            lines = final_response.splitlines()
            kept_lines = []
            removed_items = set()
            for ln in lines:
                low = ln.lower()
                matched = False
                for f in forbidden:
                    if re.search(r"\b" + re.escape(f) + r"\b", low):
                        matched = True
                        removed_items.add(f)
                        break
                if not matched:
                    kept_lines.append(ln)

            if removed_items:
                note = f"Note: removed suggestions containing your allergies/disliked foods: {', '.join(sorted(removed_items))}."
                if kept_lines:
                    final_response = note + "\n\n" + "\n".join(kept_lines)
                else:
                    final_response = (
                        note + "\n\n"
                        "I couldn't provide meal examples without recommending foods you've marked as disliked or allergic. "
                        "Please update your profile to allow broader suggestions or ask for alternatives (e.g., 'suggest peanut-free protein options')."
                    )
    except Exception as e:
        print(f"--- ASSISTANT: post-processing allergy filter failed: {e} ---")

    # Make responses more conversational and ensure the assistant ends with a question
    try:
        import re as _re
        low_resp = (final_response or "").lower()
        # If assistant already asked a similar closing question, don't duplicate
        if not no_closing_question and not _re.search(r"how else can i help|anything else i can|what else would you|anything else|is there anything else", low_resp):
            # Append the closing question to encourage continuation
            final_response = final_response + "\n\nHow else can I help?"
    except Exception:
        pass

    # Produce updated structured memory JSON via a second LLM call (keeps memory generation explicit)
    try:
        memory_prompt = (
            f"Produce an UPDATED conversation memory as a JSON object (single JSON value) using the schema described below.\n"
            f"Previous memory (may be JSON or free text): {prev_memory}\n"
            f"Conversation snippet - User: \"{last_message}\" Assistant: \"{final_response}\"\n"
            "Requirements:\n"
            "- Return ONLY valid JSON (no surrounding commentary).\n"
            "- Populate keys: preferences, recent_meals, last_recommendations, adherence_notes, important_notes.\n"
            "- recent_meals: include up to 5 recent suggested meals with an approximate calories string (e.g., \"300-400 kcal\").\n"
            "- Keep values brief and focused on facts the assistant should remember for future personalization.\n"
            "Example output:\n"
            "{\"preferences\":{\"diet_type\":\"high-protein\",\"disliked_foods\":[\"broccoli\"],\"allergies\":[\"peanuts\"],\"surgery_date\":\"2025-01-01\"},\"recent_meals\":[{\"meal\":\"Chicken soup\",\"when\":\"2025-11-12 lunch\",\"calories\":\"300-350 kcal\"}],\"last_recommendations\":[\"soft protein-rich meals\"],\"adherence_notes\":\"Ate suggested soup yesterday\",\"important_notes\":\"Prefers warm, soft textures early post-op\"}"
        )

        mem_resp = await llm.ainvoke([HumanMessage(content=memory_prompt)])
        memory_summary = mem_resp.content.strip()
    except Exception as e:
        print(f"--- ASSISTANT: Memory generation failed: {e} ---")
        memory_summary = prev_memory if prev_memory else ""

    # Also produce a README/Markdown-formatted version of the assistant output so
    # frontends that render Markdown (for example a Flutter app using
    # flutter_markdown) can display bold, headings, lists, etc. If the frontend
    # does not render Markdown, it can still use `final_response` as plain text.
    try:
        md_lines = ["# Assistant Response", ""]
        # Preserve lines, but ensure Notes get bolded for readability in Markdown
        for ln in final_response.splitlines():
            if ln.strip().startswith("Note:"):
                md_lines.append("**" + ln.strip().replace("Note:", "Note:") + "**")
            else:
                md_lines.append(ln)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("_Generated by Bariatric-GPT_")
        final_response_readme = "\n".join(md_lines)
    except Exception:
        final_response_readme = f"# Assistant Response\n\n{final_response}"

    # Build an updated compact conversation_log (last 5 user prompts and assistant responses)
    try:
        parsed = json.loads(convo_excerpt) if isinstance(convo_excerpt, str) else (convo_excerpt or {})
        if isinstance(parsed, dict):
            recent_user = parsed.get("recent_user_prompts", []) or []
            recent_assistant = parsed.get("recent_assistant_responses", []) or []
        elif isinstance(parsed, list):
            recent_user = [e.get("text") for e in parsed if isinstance(e, dict) and e.get("role") == "user"]
            recent_assistant = [e.get("text") for e in parsed if isinstance(e, dict) and e.get("role") == "assistant"]
        else:
            recent_user = []
            recent_assistant = []
    except Exception:
        recent_user = []
        recent_assistant = []

    # Append the current exchange and trim to last 5
    try:
        recent_user.append(last_message)
    except Exception:
        recent_user = [last_message]
    try:
        recent_assistant.append(final_response)
    except Exception:
        recent_assistant = [final_response]

    recent_user = recent_user[-5:]
    recent_assistant = recent_assistant[-5:]

    new_log_obj = {"recent_user_prompts": recent_user, "recent_assistant_responses": recent_assistant}
    try:
        new_log_str = json.dumps(new_log_obj)
    except Exception:
        new_log_str = "[]"

    response_state = {
        "final_response": final_response,
        "final_response_readme": final_response_readme,
        "memory": memory_summary,
        "messages": messages + [AIMessage(content=final_response)],
        "conversation_log": new_log_str,
    }

    return response_state


# ==========================================
# 7. BUILD THE SIMPLIFIED GRAPH
# ==========================================

workflow = StateGraph(MultiAgentState)

# Add preprocessor and single assistant node
workflow.add_node("preprocessor", preprocessor_agent)
workflow.add_node("assistant", assistant_agent)

# Set entry point to run preprocessor first -> assistant -> END
workflow.set_entry_point("preprocessor")
workflow.add_edge("preprocessor", "assistant")
workflow.add_edge("assistant", END)

# Compile the graph
app = workflow.compile()

print("=" * 50)
print("✅ Simplified Assistant System Compiled Successfully!")
print("=" * 50)
print("Flow: Preprocessor → Assistant")
print("=" * 50)
 
