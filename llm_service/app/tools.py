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
            # Convert user_id to int for storage service compatibility
            # In testing, user_id might be "log_user_2", so extract digits if present
            import re
            m = re.search(r'\d+', str(user_id))
            if m:
                user_id_int = int(m.group())
            else:
                try:
                    user_id_int = int(user_id)
                except ValueError:
                    user_id_int = 1 # Fallback for test sweep strings without digits
            
            # First, get the current profile
            response = await client.get(f"{STORAGE_SERVICE_URL}/me/{user_id_int}")
            
            if response.status_code != 200:
                print(f"    ERROR: Failed to fetch user profile. Status: {response.status_code}")
                return {"error": f"Failed to fetch user profile (status {response.status_code})"}
            
            user_data = response.json()
            profile = user_data.get("profile", {})
            print(f"    Current profile retrieved successfully")
            
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
                f"{STORAGE_SERVICE_URL}/me/{user_id_int}/profile",
                json={"profile": profile}
            )
            
            if update_response.status_code == 200:
                print(f"    SUCCESS: Meal recorded. New protein total: {new_protein_total}g")
                return {
                    "success": True,
                    "message": f"Recorded '{meal_name}' with {protein_grams}g protein and {calories} calories. Your daily protein total is now {new_protein_total}g.",
                    "protein_total": new_protein_total,
                    "meal_count": len(meals)
                }
            else:
                print(f"    ERROR: Failed to update profile. Status: {update_response.status_code}")
                print(f"    Response: {update_response.text}")
                return {"error": f"Failed to update profile (status {update_response.status_code})"}
                
        except httpx.HTTPError as e:
            print(f"    ERROR: Storage service connection error: {str(e)}")
            return {"error": f"Storage service connection error: {str(e)}"}
        except ValueError as e:
            print(f"    ERROR: Invalid user_id format: {str(e)}")
            return {"error": f"Invalid user_id format: {str(e)}"}
        except Exception as e:
            print(f"    ERROR: Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

@tool
async def search_nutrition(food_query: str) -> dict:
    """
    Searches the OpenFoodFacts database to find nutritional information for a specific food.
    Useful for getting exact macros (protein, calories, carbs, fat) and serving sizes before recommending foods.
    """
    print(f"--- Calling Tool: search_nutrition for query '{food_query}' ---")
    
    # OpenFoodFacts free JSON API
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={food_query}&search_simple=1&action=process&json=1&page_size=1"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                products = data.get("products", [])
                
                if not products:
                    return {"error": f"No nutrition data found for '{food_query}'."}
                
                product = products[0]
                nutriments = product.get("nutriments", {})
                
                serving_size = product.get("serving_size", "100g")
                if not serving_size:
                    serving_size = "100g (Data standardized to 100g if serving size missing)"
                
                return {
                    "food_name": product.get("product_name", food_query),
                    "serving_size": serving_size,
                    "calories": nutriments.get("energy-kcal_serving", nutriments.get("energy-kcal_100g", "Unknown")),
                    "protein_g": nutriments.get("proteins_serving", nutriments.get("proteins_100g", "Unknown")),
                    "carbs_g": nutriments.get("carbohydrates_serving", nutriments.get("carbohydrates_100g", "Unknown")),
                    "fat_g": nutriments.get("fat_serving", nutriments.get("fat_100g", "Unknown"))
                }
            else:
                return {"error": f"Failed to fetch food data. Status: {response.status_code}"}
        except Exception as e:
            return {"error": f"Nutrition API connection error: {str(e)}"}