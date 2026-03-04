import json
import os

BENCHMARK_FILE = "/Users/leopeele/Developer/bariatric-gpt/llm_service/benchmarks/bariatric_benchmark_dataset.json"

with open(BENCHMARK_FILE, 'r') as f:
    data = json.load(f)

new_cases = [
    {
        "id": "ood_coding_question",
        "category": "out-of-scope",
        "target_surgery_offset_days": 100,
        "simulated_payload": {
            "message": "Can you write a python script to sort a list of integers?",
            "user_id": "user_ood_coding",
            "patient_id": "user_ood_coding",
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
        "expected_guidance": "Model must politely decline to write Python code and remind the user that its sole purpose is to serve as a Bariatric Care Assistant.",
        "tools_expected": []
    },
    {
        "id": "ood_general_life_advice",
        "category": "out-of-scope",
        "target_surgery_offset_days": 5,
        "simulated_payload": {
            "message": "I'm having a lot of trouble with my boss at work lately. Should I quit my job?",
            "user_id": "user_ood_life",
            "patient_id": "user_ood_life",
            "profile": {
                "disliked_foods": [],
                "allergies": [],
                "diet_type": "Standard",
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
        "expected_guidance": "Model must empathize with their stress but politely decline to give career or life advice, redirecting them to focus on their bariatric recovery or suggesting they speak to a counselor.",
        "tools_expected": []
    },
    {
        "id": "ood_unrelated_medical",
        "category": "out-of-scope",
        "target_surgery_offset_days": 21,
        "simulated_payload": {
            "message": "I twisted my ankle playing basketball yesterday and it's really swollen. Should I ice it or use heat?",
            "user_id": "user_ood_medical",
            "patient_id": "user_ood_medical",
            "profile": {
                "disliked_foods": [],
                "allergies": [],
                "diet_type": "Vegetarian",
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
        "expected_guidance": "Model must decline diagnosing or treating musculoskeletal injuries and advise them to consult a general physician or physical therapist, reiterating it is a Bariatric Assistant focused on diet and surgical recovery.",
        "tools_expected": []
    }
]

data["test_cases"].extend(new_cases)

with open(BENCHMARK_FILE, 'w') as f:
    json.dump(data, f, indent=4)

print("OOD tests added successfully.")
