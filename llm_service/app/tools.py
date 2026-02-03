from langchain_core.tools import tool
import httpx
import os
import json
from datetime import datetime

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

@tool
async def record_meal(user_id: str, meal_name: str, protein_grams: float, calories: float) -> dict:
    """
    Records a meal for the user, adding it to their meals list and updating daily protein totals.
    
    Args:
        user_id: The user's ID
        meal_name: Description of the meal (e.g., "Chicken breast and rice")
        protein_grams: Estimated protein content in grams
        calories: Estimated calorie content
    
    Returns:
        Dictionary with success status and message
    """
    print(f"--- Calling Tool: record_meal for user {user_id} ---")
    print(f"    Meal: {meal_name}, Protein: {protein_grams}g, Calories: {calories}")
    
    async with httpx.AsyncClient() as client:
        try:
            # First, get the current profile
            response = await client.get(f"{STORAGE_SERVICE_URL}/me/{user_id}")
            
            if response.status_code != 200:
                return {"error": "Failed to fetch user profile"}
            
            user_data = response.json()
            profile = user_data.get("profile", {})
            
            # Get current meals list or create new one (use 'todays_meals' to match the Meals screen)
            meals = profile.get("todays_meals", [])
            
            # Add the new meal
            new_meal = {
                "food": meal_name,  # Use 'food' key to match Meals screen format
                "protein": protein_grams,
                "calories": calories
            }
            meals.append(new_meal)
            
            # Update protein_today
            current_protein = profile.get("protein_today", 0)
            new_protein_total = current_protein + protein_grams
            
            # Update profile with new meals and protein total
            profile["todays_meals"] = meals  # Save to 'todays_meals' field
            profile["protein_today"] = new_protein_total
            
            # Update protein history
            today = datetime.now().strftime("%Y-%m-%d")
            protein_history = profile.get("protein_history", {})
            protein_history[today] = new_protein_total
            profile["protein_history"] = protein_history
            
            # Save updated profile to the correct endpoint
            update_response = await client.put(
                f"{STORAGE_SERVICE_URL}/me/{user_id}/profile",
                json={"profile": profile}
            )
            
            if update_response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Recorded '{meal_name}' with {protein_grams}g protein and {calories} calories. Your daily protein total is now {new_protein_total}g.",
                    "protein_total": new_protein_total,
                    "meal_count": len(meals)
                }
            else:
                return {"error": "Failed to update profile"}
                
        except httpx.HTTPError as e:
            return {"error": f"Storage service connection error: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}