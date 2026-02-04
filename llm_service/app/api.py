from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from .graph_medical_multiagent import app, generate_and_persist_memory  # Import the multi-agent graph
from langchain_core.messages import HumanMessage

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
    
    print(f"\n{'='*60}")
    print(f"New Chat Request from user: {request.user_id}")
    print(f"Message: {request.message}")
    print(f"Patient ID: {request.patient_id if request.patient_id else 'None'}")
    print(f"Profile sent: {request.profile if request.profile else 'None'}")
    print(f"{'='*60}\n")
    
    # 1. Define the initial state for the multi-agent graph
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": request.user_id,
        "patient_id": request.patient_id,
        "profile": request.profile,
        "memory": request.memory,
        "conversation_log": request.conversation_log,
        "next_agent": "",
        "medical_response": None,
        "data_response": None,
        "final_response": None
    }
    
    try:
        # 2. Invoke the compiled multi-agent graph
        # The graph will automatically route through supervisor → agents → synthesizer
        result_state = await app.ainvoke(initial_state)

        # 3. Extract the final synthesized response (plain and Markdown) and updated memory
        final_answer = result_state.get("final_response")
        final_answer_readme = result_state.get("final_response_readme")
        updated_memory = result_state.get("memory")

        # Robust fallback: prefer the graph's message if final_response missing
        if not final_answer and result_state.get("messages"):
            try:
                final_answer = result_state["messages"][-1].content
            except Exception:
                final_answer = None
        if not final_answer:
            final_answer = "I couldn't process that request."
        
        print(f"\n{'='*60}")
        print(f"Response generated successfully")
        print(f"Sending response back to user")
        print(f"{'='*60}\n")
        
        # Include updated memory and conversation_log (if any) so the gateway can persist them
        # Provide both Markdown (`response_markdown`) and plain-text (`response_text`).
        # Prefer Markdown for the primary `response` when available so frontends
        # that render Markdown can display rich formatting. Frontends that do not
        # render Markdown can use `response_text`.
        resp = {
            "response": final_answer_readme if final_answer_readme else final_answer,
            "response_markdown": final_answer_readme,
            "response_text": final_answer,
        }
        if updated_memory is not None:
            resp["memory"] = updated_memory
        
        # Schedule Async Memory Update
        # Only trigger if we have a valid response and userID.
        # This will run AFTER the response is sent to the user.
        if final_answer and request.user_id:
            background_tasks.add_task(
                generate_and_persist_memory,
                user_id=request.user_id,
                prev_memory=request.memory if request.memory else "",
                last_message=request.message,
                assistant_response=final_answer
            )
        # If the agent graph returned a compact conversation_log, include it in the response
        # so the gateway can persist the authoritative recent-5 transcript.
        conv_log = result_state.get("conversation_log")
        if conv_log is not None:
            resp["conversation_log"] = conv_log
        # If debug requested, include raw agent outputs for inspection
        if request.debug:
            resp["medical_response"] = result_state.get("medical_response")
            resp["data_response"] = result_state.get("data_response")
            resp["state_messages"] = [m.content for m in result_state.get("messages", [])]
        return resp
    
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR: ERROR invoking multi-agent graph: {e}")
        print(f"{'='*60}\n")
        # Friendly fallback so the app can always show a response
        fallback = (
            "I'm having a temporary issue accessing tools, but I'm still here to help with "
            "general guidance. Could you rephrase your question, or ask about diet, recovery, "
            "activity, or typical timelines after bariatric surgery?"
        )
        return {"response": fallback}