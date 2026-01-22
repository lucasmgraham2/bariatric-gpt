# Multi-Agent Medical Assistant System - Setup Guide

## Quick Start

### 1. **Install Ollama** (If not already installed)
```bash
# Download from: https://ollama.com/download
# Pull the model we're using:
ollama pull deepseek-r1:8b
```

### 2. **Setup Database with Sample Patients**
```markdown
# AI Medical Assistant - Setup & Notes (Updated)

This document replaces the older "multi-agent" design notes. The system has been simplified to a compact, more deterministic flow to improve reliability and maintainability while preserving the same capabilities:

- A small preprocessor expands shorthand user replies ("the second option", "2nd", "that one").
- A single consolidated assistant node handles intent detection, optional patient-data access, meal suggestions, medical guidance, deterministic allergen filtering, and memory generation.
- Conversation history is stored as a compact rolling snippet (last 5 user prompts + last 5 assistant responses) and is supplied to the assistant for context.
- The assistant returns both plain text and a Markdown/README-formatted response so frontends can render bold/headers/lists correctly.

---

## Quick Start

### 1. Install Ollama (if using local models)
```powershell
# Download/install from: https://ollama.com/download
# Pull the model used for local testing (optional):
ollama pull deepseek-r1:8b
```

### 2. Populate sample data (optional)
```powershell
# Ensure PostgreSQL is running
python scripts/create_sample_patients.py
```

### 3. Start services (typical)
Open terminals and run the services you need. Example commands:

Terminal 1 - Storage Service (Port 8002)
```powershell
python storage_service/main_simple.py
```

Terminal 2 - LLM Service (Port 8001)
```powershell
cd llm_service
python -m app.main
```

Terminal 3 - API Gateway (Port 8000)
```powershell
python api_gateway/main_simple.py
```

Terminal 4 - Flutter App
```powershell
cd flutter_frontend
flutter run
```

---

## Current Architecture (Simplified)

```
FLUTTER FRONTEND (UI)
  • Chat screen -> sends /chat requests to API Gateway
        ↓ HTTP
API GATEWAY (Port 8000)
  • Auth proxy, fetches profile/memory/conversation_log
  • Forwards message + compact context to LLM Service
        ↓ HTTP
LLM SERVICE (Port 8001)
  • Preprocessor (expands short replies / resolves ordinals)
  • Assistant Agent (single node): intent detection, optional patient tools,
    deterministic allergy/dislike filtering, generates memory JSON,
    and produces two response formats (plain text + Markdown/README)
        ↓
STORAGE SERVICE (Port 8002)
  • PostgreSQL-backed storage for users, profiles, memory, conversation_log
```

Key differences from the original multi-agent design:
- The previous Supervisor → Medical/Data → Synthesizer chain has been consolidated.
- A deterministic preprocessor now handles shorthand expansion before the assistant.
- Memory generation is still explicit: the assistant produces a JSON memory object which the API Gateway stores on the account (server-side-only access).

---

## How the chat flow works (summary)

1. Frontend posts a message to `/chat` on the API Gateway.
2. Gateway loads the user's `profile`, `memory`, and the compact `conversation_log` (rolling last-5 user prompts + last-5 assistant responses) and builds the initial state.
3. LLM Service runs the preprocessor to expand shorthand replies (ordinals, "that one", simple yes/no) using the most recent assistant text as context.
4. The assistant agent runs once and:
   - Detects intent (grocery list, calorie breakdown, recipe, profile query, meal suggestions, or general medical guidance).
   - Optionally calls a patient data tool when enabled and when patient_id is present.
   - Produces a concise, safe response.
   - Applies a deterministic filter to remove suggestions containing allergies or disliked foods (exact matches / word-boundary); Gateway stores which items were removed.
   - Generates a structured memory JSON (keys: preferences, recent_meals, last_recommendations, adherence_notes, important_notes).
5. The LLM Service returns:
   - `final_response` (plain text)
   - `final_response_readme` (Markdown/README formatted)
   - `memory` (JSON string)
   - `messages` (updated conversation messages)
6. Gateway persists the new memory (server-side only) and appends/normalizes the `conversation_log` into the two-array compact shape.
7. Frontend receives the response and renders Markdown when available (uses `final_response_readme`).

---

## Example interactions (now)

User: "Which of these sounds best? 1) Chicken salad, 2) Vegetable quinoa bowl, 3) Lentil soup"
Assistant (initial): "1) Chicken salad — high protein, light dressing\n2) Vegetable quinoa bowl — balanced, vegan-friendly\n3) Lentil soup — hearty, good fiber"
User: "the second option"

Flow:
Preprocessor resolves "the second option" -> expands to the selected option text ("Vegetable quinoa bowl"). Assistant receives the explicit selection and responds with details or next steps.

User: "Can you make a grocery list for that?"
Assistant: Produces a consolidated grocery list based on the selected item (or recent meal suggestions).

Note: If the preprocessor cannot confidently map the ordinal (no parseable options found), the assistant will ask a short clarifying question rather than guessing.

---

## Memory & Conversation Log

- Conversation log storage format (stored as JSON string in the DB):

```json
{
  "recent_user_prompts": ["...last 5 user messages..."],
  "recent_assistant_responses": ["...last 5 assistant replies..."]
}
```

- Memory is stored as a JSON object on the user's account and is only writable/readable by backend services (protected by service-key). The assistant returns an updated `memory` which the Gateway persists.

---

## Deterministic Protections

- Allergy / disliked-food enforcement is performed deterministically after the assistant response: any lines containing exact word-boundary matches of recorded allergies/dislikes are removed. If all suggestions are removed the assistant returns a short note and asks for permission or requests alternative constraints.
- Service-key protected endpoints: only internal services with the correct service key may read/modify memory or conversation logs.

---

## Troubleshooting & Performance notes

- LLM responses may still take several seconds depending on model & hardware. The simplified single-node flow reduces hops and generally improves latency vs a multi-node orchestration.
- If shorthand replies (ordinals) are misinterpreted, check the `conversation_log` stored in the account to ensure the assistant's last message contains parseable enumerations (numbered lines, bullets, or an inline "Options:" list).
- If allergen filtering removes content unexpectedly, update `Profile → Edit` to add synonyms or broaden allowed alternatives; we can improve matching heuristics later.

---

## Files of interest (where behavior lives)

```
llm_service/
├── app/
│   ├── main.py                      # FastAPI server for the LLM service
│   ├── api.py                       # Chat endpoint that invokes the graph
│   ├── graph_medical_multiagent.py  # Preprocessor + single assistant node
│   └── tools.py                     # Patient data retrieval helpers

api_gateway/
└── main_simple.py                   # Normalizes logs, fetches/persists memory

storage_service/
└── main_simple.py                   # DB endpoints for users, memory, conversation_log

flutter_frontend/
├── lib/services/ai_service.dart     # Calls /chat and exposes plain + markdown fields
└── lib/screens/ai_assistant_screen.dart # Renders messages (Markdown when available)

scripts/
└── create_sample_patients.py        # Sample patient data
```

---

## Success Indicators (updated)

You should see:

1. All services you need are running (check terminal logs).
2. The Flutter app connects and the AI Assistant screen loads without errors.
3. Simple medical questions return concise guidance.
4. Short-hand replies ("the first", "2nd", "that one") are expanded correctly when the assistant previously presented options.
5. Conversation memory updates persist on the account (check the `memory` field in the DB).
6. Frontend renders bold/text formatting properly using the Markdown field when available.

---

If you want the older multi-agent routing restored (Supervisor + Medical + Data + Synthesizer), that code is still in the repo history but the active flow is the simplified preprocessor → assistant design described above.

If you'd like, I can also:
- Add more robust synonym matching for allergen enforcement.
- Make the Markdown output richer (convert numbered lists and bullets into proper Markdown lists).
- Add unit tests for ordinal parsing and conversation_log conversions.

``` 
api_gateway/
