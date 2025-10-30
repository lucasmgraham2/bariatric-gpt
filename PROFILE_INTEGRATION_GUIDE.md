# Profile Integration Guide

This guide explains how to add user profile and patient data integration to the chat system.

## Current State

✅ **What Works Now:**
- Users can chat with AI assistant about general bariatric surgery topics
- Authentication system tracks user_id
- Patient data tools exist but are disabled (feature flag)
- System is fast with llama3.2:3b model (5-10 second responses)

❌ **What's Not Connected Yet:**
- Patient profiles aren't linked to user accounts
- Chat doesn't access personal medical data
- Patient ID input removed from UI (ready for auto-linking)

---

## How to Enable Profile Integration

### Step 1: Create User-Patient Link in Storage Service

Add a `patient_id` column to the Users table:

```python
# In storage_service/main_simple.py

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    salt = Column(String)
    patient_id = Column(Integer, nullable=True)  # ADD THIS LINE
```

Run migration to update database:
```sql
ALTER TABLE users ADD COLUMN patient_id INTEGER;
```

### Step 2: Auto-Link Patient ID in API Gateway

Modify the `/chat` endpoint to fetch patient_id from user profile:

```python
# In api_gateway/main_simple.py

@app.post("/chat")
async def chat_with_agent(chat_data: ChatRequest, authorization: Optional[str] = Header(None)):
    # ... existing auth code ...
    
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # FETCH PATIENT ID FROM USER PROFILE
    async with httpx.AsyncClient() as client:
        user_response = await client.get(f"{STORAGE_URL}/me/{user_id}")
        user_data = user_response.json()
        patient_id = user_data.get("patient_id")  # Get linked patient ID
    
    llm_payload = {
        "message": chat_data.message,
        "user_id": str(user_id),
        "patient_id": str(patient_id) if patient_id else None  # Auto-linked!
    }
    
    # ... rest of code ...
```

### Step 3: Enable Patient Tools in LLM Service

Turn on the feature flag:

```python
# In llm_service/app/graph_medical_multiagent.py

# Change this line:
ENABLE_PATIENT_TOOLS = True  # Was False
```

### Step 4: Add Profile Management UI (Optional)

Create a Profile screen in Flutter where users can:
- View their linked patient ID
- Update medical history
- View progress charts

---

## Testing After Integration

1. **Create a patient record:**
   ```powershell
   python scripts/create_sample_patients.py
   ```

2. **Link user to patient:**
   ```sql
   UPDATE users SET patient_id = 1 WHERE id = <your_user_id>;
   ```

3. **Test in app:**
   - Login
   - Ask: "What's my current weight?"
   - Should retrieve your patient data automatically

---

## Extensibility Notes

### Where Patient Data is Used

1. **Supervisor Agent** (`graph_medical_multiagent.py` line ~50)
   - Routes to Data Agent if patient_id exists and query needs data

2. **Data Agent** (`graph_medical_multiagent.py` line ~135)
   - Calls `get_patient_data` tool to fetch from database
   - Currently disabled by `ENABLE_PATIENT_TOOLS` flag

3. **Synthesizer Agent** (`graph_medical_multiagent.py` line ~190)
   - Combines medical guidance with patient-specific data

### Adding New Patient Tools

Create new tools in `llm_service/app/tools.py`:

```python
@tool
async def get_patient_vitals(patient_id: str) -> dict:
    """Fetches latest vitals (blood pressure, heart rate, etc.)"""
    # Implementation here
    pass

@tool
async def get_patient_labs(patient_id: str) -> dict:
    """Fetches recent lab results"""
    # Implementation here
    pass
```

Then bind them to agents in `graph_medical_multiagent.py`:

```python
from .tools import get_patient_data, get_patient_vitals, get_patient_labs

# In data_agent function:
tools = [get_patient_data, get_patient_vitals, get_patient_labs]
```

---

## Architecture Diagram

```
User Login → API Gateway → Storage Service
     ↓                           ↓
   Token                    patient_id
     ↓                           ↓
   Chat Request ← auto-linked ← User Profile
     ↓
   LLM Service
     ↓
   Supervisor (checks ENABLE_PATIENT_TOOLS flag)
     ↓
   ├─→ Medical Agent (general guidance)
     └─→ Data Agent (fetch patient data if enabled)
           ↓
         Synthesizer (combine responses)
           ↓
         Response to App
```

---

## Quick Checklist for Future Implementation

- [ ] Add `patient_id` column to Users table
- [ ] Create migration script
- [ ] Update `/auth/me` endpoint to return patient_id
- [ ] Modify `/chat` endpoint to auto-fetch patient_id
- [ ] Set `ENABLE_PATIENT_TOOLS = True`
- [ ] Test with sample patients
- [ ] Add Profile screen in Flutter
- [ ] Add patient creation/update endpoints
- [ ] Implement additional patient tools (vitals, labs, etc.)
- [ ] Add data visualization (weight charts, progress tracking)

---

## Current File Locations

**Feature Flag:**
- `llm_service/app/graph_medical_multiagent.py` line 15

**Patient Tools:**
- `llm_service/app/tools.py`

**API Integration Points:**
- `api_gateway/main_simple.py` line 95 (chat endpoint)
- `flutter_frontend/lib/services/ai_service.dart` line 9

**Comments Marking Extension Points:**
- Search codebase for "Future" or "TODO" comments
