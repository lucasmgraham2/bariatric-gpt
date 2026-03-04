import json
import os

BENCHMARK_FILE = "/Users/leopeele/Developer/bariatric-gpt/llm_service/benchmarks/bariatric_benchmark_dataset.json"

with open(BENCHMARK_FILE, 'r') as f:
    data = json.load(f)

new_cases = [
    {
        "id": "nutrition_lookup_chicken",
        "category": "nutrition",
        "target_surgery_offset_days": 100,
        "simulated_payload": {
            "message": "How much protein is in 100g of chicken breast? I need to know for my macros.",
            "user_id": "user_nutrition_chicken",
            "patient_id": "user_nutrition_chicken",
            "profile": {
                "disliked_foods": [],
                "allergies": [],
                "diet_type": "Standard",
                "weight": 250.0,
                "weight_unit": "lbs",
                "date_of_birth": "1985-05-15",
                "surgery_date": "DYNAMIC_CALCULATED_DATE",
                "activity_level": "Active",
                "medications": []
            },
            "memory": "",
            "conversation_log": "[]"
        },
        "expected_guidance": "Model should use the nutrition context from the Dietitian agent (OpenFoodFacts) to provide exact macronutrients for 100g of chicken breast, specifically citing the protein amount. It MUST use the format 'Here are the exact macros from OpenFoodFacts:'",
        "tools_expected": ["search_nutrition"]
    },
    {
        "id": "nutrition_lookup_edamame_phase3",
        "category": "nutrition",
        "target_surgery_offset_days": 21,
        "simulated_payload": {
            "message": "I'm in Phase 3. Can I have 1 cup of edamame? What are the macros?",
            "user_id": "user_nutrition_edamame",
            "patient_id": "user_nutrition_edamame",
            "profile": {
                "disliked_foods": [],
                "allergies": [],
                "diet_type": "Vegetarian",
                "weight": 250.0,
                "weight_unit": "lbs",
                "date_of_birth": "1985-05-15",
                "surgery_date": "DYNAMIC_CALCULATED_DATE",
                "activity_level": "Sedentary",
                "medications": []
            },
            "memory": "",
            "conversation_log": "[]"
        },
        "expected_guidance": "Model must fetch nutritional data for edamame using the search_nutrition tool. Model must note the 'Here are the exact macros from OpenFoodFacts:' format. Model must warn that edamame needs to be purely blended/pureed to be safe for Phase 3.",
        "tools_expected": ["search_nutrition"]
    }
]

data["test_cases"].extend(new_cases)

with open(BENCHMARK_FILE, 'w') as f:
    json.dump(data, f, indent=4)

print("Tests added successfully.")
