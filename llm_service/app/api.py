from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .graph import app  # Import the compiled LangGraph app
from langchain_core.messages import HumanMessage

router = APIRouter()

# This model matches the payload from the API Gateway
class ChatRequest(BaseModel):
    message: str
    user_id: str
    patient_id: Optional[str] = None

@router.post("/invoke_agent_graph")
async def invoke_chat(request: ChatRequest):
    """
    Receives a user message and runs it through the LangGraph agent.
    """
    
    # 1. Define the initial state for the graph
    # We use a HumanMessage for the first message
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": request.user_id,
        "patient_id": request.patient_id
    }
    
    try:
        # 2. Invoke the compiled graph
        # .ainvoke() runs the graph from start to finish
        result_state = await app.ainvoke(initial_state)
        
        # 3. Get the final answer
        # The last message in the state is the AI's final response
        final_answer = result_state["messages"][-1].content
        
        return {"response": final_answer}
    
    except Exception as e:
        print(f"Error invoking graph: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")