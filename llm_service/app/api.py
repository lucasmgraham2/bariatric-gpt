from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .graph_medical_multiagent import app  # Import the multi-agent graph
from langchain_core.messages import HumanMessage

router = APIRouter()

# This model matches the payload from the API Gateway
class ChatRequest(BaseModel):
    message: str
    user_id: str
    patient_id: Optional[str] = None  # Reserved for future profile integration
    profile: Optional[dict] = None
    memory: Optional[str] = None

@router.post("/invoke_agent_graph")
async def invoke_chat(request: ChatRequest):
    """
    Receives a user message and runs it through the Multi-Agent Medical System.
    The system automatically routes queries to appropriate specialist agents.
    
    Currently patient_id is optional/null. Future: will be auto-populated from
    user profile to enable personalized medical guidance and progress tracking.
    """
    
    print(f"\n{'='*60}")
    print(f"📨 New Chat Request from user: {request.user_id}")
    print(f"💬 Message: {request.message}")
    print(f"🏥 Patient ID: {request.patient_id if request.patient_id else 'None'}")
    print(f"👤 Profile sent: {request.profile if request.profile else 'None'}")
    print(f"{'='*60}\n")
    
    # 1. Define the initial state for the multi-agent graph
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": request.user_id,
        "patient_id": request.patient_id,
        "profile": request.profile,
        "memory": request.memory,
        "next_agent": "",
        "medical_response": None,
        "data_response": None,
        "final_response": None
    }
    
    try:
        # 2. Invoke the compiled multi-agent graph
        # The graph will automatically route through supervisor → agents → synthesizer
        result_state = await app.ainvoke(initial_state)

        # 3. Extract the final synthesized response and updated memory
        final_answer = result_state.get("final_response")
        updated_memory = result_state.get("memory")

        if not final_answer:
            # Fallback if synthesis failed
            final_answer = result_state["messages"][-1].content if result_state["messages"] else "I couldn't process that request."
        
        print(f"\n{'='*60}")
        print(f"✅ Response generated successfully")
        print(f"📤 Sending response back to user")
        print(f"{'='*60}\n")
        
        # Include updated memory (if any) in the response so the gateway can persist it
        resp = {"response": final_answer}
        if updated_memory is not None:
            resp["memory"] = updated_memory
        return resp
    
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERROR invoking multi-agent graph: {e}")
        print(f"{'='*60}\n")
        # Friendly fallback so the app can always show a response
        fallback = (
            "I'm having a temporary issue accessing tools, but I'm still here to help with "
            "general guidance. Could you rephrase your question, or ask about diet, recovery, "
            "activity, or typical timelines after bariatric surgery?"
        )
        return {"response": fallback}