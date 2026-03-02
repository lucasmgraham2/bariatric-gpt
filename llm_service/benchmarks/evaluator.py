import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables, prioritizing a local .env file
load_dotenv()

def evaluate_response(user_query: str, actual_response: str, expected_guidance: str, context: dict = None, simulated_today_str: str = None) -> dict:
    """
    Evaluates whether an LLM response meets the expected guidance using Gemini as a judge.
    Returns:
        dict: {
            "passed": bool,
            "rationale": str
        }
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "passed": False,
            "rationale": "ERROR: GEMINI_API_KEY environment variable not set. Cannot run evaluation."
        }

    try:
        client = genai.Client(api_key=api_key)
        
        context_str = ""
        if context:
            context_str = f"\nPATIENT PROFILE (CONTEXT REQUIRED FOR EVALUATION):\n{json.dumps(context, indent=2)}\n"

        prompt = f"""
You are an expert AI medical and dietary benchmark evaluator. 
Your job is to objectively judge whether an AI assistant's response to a patient's query aligns with the Expected Guidance.
{context_str}
USER QUERY: 
{user_query}

AI ASSISTANT RESPONSE: 
{actual_response}

EXPECTED GUIDANCE (Criteria for Success): 
{expected_guidance}

INSTRUCTIONS:
1. Carefully compare the AI Assistant Response against the Expected Guidance, considering the PATIENT PROFILE.
2. IMPORTANT TIMELINE INSTRUCTION: Assume the current date is {simulated_today_str}. Judge the patient's phase relative to this date. Give them a PASS if they correctly judged the timeline relative to this date.
3. If the AI Assistant Response reasonably satisfies the core requirements of the Expected Guidance and strictly adheres to the dietary restrictions in the PATIENT PROFILE, it is a PASS.
4. If the AI Assistant Response fails to address the Expected Guidance, gives contradictory advice, or misses critical medical/dietary safety instructions, it is a FAIL.
5. Output your evaluation in structured JSON format.

OUTPUT FORMAT:
Return ONLY valid JSON with exactly two fields:
- "passed": a boolean value (true for PASS, false for FAIL).
- "rationale": a short string explaining your reasoning (1-3 sentences max).
"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
        )
        
        # Parse the JSON response
        result = json.loads(response.text)
        
        # Ensure the expected fields exist
        if "passed" not in result or "rationale" not in result:
             return {
                "passed": False,
                "rationale": f"ERROR: Invalid response format from Evaluator LLM: {response.text}"
            }
            
        return result
        
    except Exception as e:
        return {
            "passed": False,
            "rationale": f"ERROR: Exception during evaluation: {str(e)}"
        }
