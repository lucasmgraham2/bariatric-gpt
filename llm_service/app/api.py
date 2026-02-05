from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from .graph_medical_multiagent import app, generate_and_persist_memory
from langchain_core.messages import HumanMessage, AIMessage
import json

router = APIRouter()

# This model matches the payload from the API Gateway
class ChatRequest(BaseModel):
    message: str
    user_id: str
    patient_id: Optional[str] = None  # Reserved for future profile integration
    profile: Optional[dict] = None
    memory: Optional[str] = None
    conversation_log: Optional[str] = None
    debug: Optional[bool] = False

@router.post("/invoke_agent_graph")
async def invoke_chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Receives a user message and runs it through the Multi-Agent Medical System.
    The system automatically routes queries to appropriate specialist agents.
    
    Currently patient_id is optional/null. Future: will be auto-populated from
    user profile to enable personalized medical guidance and progress tracking.
    """
    
    # Reconstruct full conversation history from conversation_log
    message_history = []
    if request.conversation_log:
        try:
            parsed = json.loads(request.conversation_log) if isinstance(request.conversation_log, str) else request.conversation_log
            if isinstance(parsed, dict):
                recent_user = parsed.get("recent_user_prompts", []) or []
                recent_assistant = parsed.get("recent_assistant_responses", []) or []
                for i in range(min(len(recent_user), len(recent_assistant))):
                    message_history.append(HumanMessage(content=recent_user[i]))
                    message_history.append(AIMessage(content=recent_assistant[i]))
        except:
            pass
    
    message_history.append(HumanMessage(content=request.message))
    
    initial_state = {
        "messages": message_history,
        "user_id": request.user_id,
        "patient_id": request.patient_id,
        "profile": request.profile,
        "memory": request.memory,
        "conversation_log": request.conversation_log,
    }
    
    try:
        result_state = await app.ainvoke(initial_state)
        
        final_answer = result_state.get("final_response")
        final_answer_readme = result_state.get("final_response_readme")
        
        if not final_answer and result_state.get("messages"):
            try:
                final_answer = result_state["messages"][-1].content
            except:
                pass
        if not final_answer:
            final_answer = "I couldn't process that request."
        
        resp = {
            "response": final_answer_readme if final_answer_readme else final_answer,
            "response_markdown": final_answer_readme,
            "response_text": final_answer,
        }
        
        if result_state.get("memory"):
            resp["memory"] = result_state["memory"]
        
        if result_state.get("conversation_log"):
            resp["conversation_log"] = result_state["conversation_log"]
        
        if final_answer and request.user_id:
            background_tasks.add_task(
                generate_and_persist_memory,
                user_id=request.user_id,
                prev_memory=request.memory or "",
                last_message=request.message,
                assistant_response=final_answer
            )
        
        if request.debug:
            resp["medical_response"] = result_state.get("medical_response")
            resp["data_response"] = result_state.get("data_response")
            resp["state_messages"] = [m.content for m in result_state.get("messages", [])]
        
        return resp
    
    except Exception as e:
        print(f"Error invoking agent graph: {e}")
        return {"response": "I'm having trouble right now. Please try again."}