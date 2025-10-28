from langchain_core.tools import tool
import httpx
import os

# This is the internal URL for your storage service
# Make sure this is correct.
STORAGE_SERVICE_URL = "http://localhost:8002" 

@tool
async def get_patient_data(patient_id: str) -> dict:
    """
    Fetches patient data for a specific patient_id from the storage service.
    Only use this if you are given a patient_id.
    """
    print(f"--- Calling Tool: get_patient_data for patient {patient_id} ---")
    
    # TODO: Your storage_service needs to have this endpoint:
    # GET /patients/{patient_id}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{STORAGE_SERVICE_URL}/patients/{patient_id}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"error": "Patient not found"}
            else:
                response.raise_for_status()
                return {"error": "An unknown error occurred"}
        except httpx.HTTPError as e:
            return {"error": f"Storage service connection error: {str(e)}"}