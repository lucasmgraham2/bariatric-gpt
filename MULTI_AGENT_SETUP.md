# 🤖 Multi-Agent Medical Assistant System - Setup Guide

## 🎯 Quick Start

### 1. **Install Ollama** (If not already installed)
```bash
# Download from: https://ollama.com/download
# Pull the model we're using:
ollama pull deepseek-r1:8b
```

### 2. **Setup Database with Sample Patients**
```bash
# Make sure PostgreSQL is running
python scripts/create_sample_patients.py
```

### 3. **Start All Services**

Open **4 terminals**:

**Terminal 1 - Storage Service (Port 8002)**
```bash
python storage_service/main_simple.py
```

**Terminal 2 - LLM Service (Port 8001)**
```bash
cd llm_service
python -m app.main
```

**Terminal 3 - API Gateway (Port 8000)**
```bash
python api_gateway/main_simple.py
```

**Terminal 4 - Flutter App**
```bash
cd flutter_frontend
flutter run
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│              FLUTTER FRONTEND                        │
│  • AI Assistant Screen                               │
│  • Patient ID input (optional)                       │
│  • Real-time chat interface                          │
└──────────────────────────────────────────────────────┘
                        ↓ HTTP REST
┌──────────────────────────────────────────────────────┐
│           API GATEWAY (Port 8000)                    │
│  • Authentication & Token Management                 │
│  • Routes /chat to LLM Service                       │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│         LLM SERVICE (Port 8001)                      │
│  ┌────────────────────────────────────────────────┐  │
│  │     SUPERVISOR AGENT (Router)                  │  │
│  │  • Analyzes query intent                       │  │
│  │  • Routes to specialist agents                 │  │
│  └────────────────────────────────────────────────┘  │
│              ↓                      ↓                 │
│  ┌──────────────────┐    ┌──────────────────┐        │
│  │ MEDICAL AGENT    │    │ DATA AGENT       │        │
│  │ • Medical Q&A    │    │ • Fetches patient│        │
│  │ • Guidelines     │    │   data from DB   │        │
│  │ • Best practices │    │ • Retrieves info │        │
│  └──────────────────┘    └──────────────────┘        │
│              ↓                      ↓                 │
│  ┌────────────────────────────────────────────────┐  │
│  │       RESPONSE SYNTHESIZER                     │  │
│  │  • Combines agent outputs                      │  │
│  │  • Creates coherent final response             │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│      STORAGE SERVICE (Port 8002)                     │
│  • PostgreSQL Database                               │
│  • Patient records                                   │
│  • User authentication                               │
└──────────────────────────────────────────────────────┘
```

---

## 💬 Example Interactions

### **Medical Questions (No patient data needed)**
```
User: "What are the best foods after bariatric surgery?"

Flow:
Supervisor → Medical Agent → Synthesizer

Response: "After bariatric surgery, focus on protein-rich foods like lean 
meats, eggs, and Greek yogurt. Start with soft foods and gradually advance 
texture. Avoid sugar, fried foods, and carbonated drinks. This is general 
guidance - follow your surgeon's specific recommendations."
```

### **Data Queries (Requires patient ID)**
```
User: "What's patient 1's current weight?"
Patient ID: 1

Flow:
Supervisor → Data Agent → Synthesizer

Response: "Patient John Smith's current weight is 220.0 lbs, down from 
a starting weight of 310.0 lbs. That's a loss of 90 lbs since their 
gastric bypass surgery 6 months ago."
```

### **Complex Queries (Uses both agents)**
```
User: "Is patient 2's progress good?"
Patient ID: 2

Flow:
Supervisor → Medical Agent + Data Agent → Synthesizer

Response: "Patient Sarah Johnson has lost 85 lbs in one year since her 
sleeve gastrectomy (starting: 250 lbs, current: 165 lbs). Her BMI of 27.8 
is now in the overweight range, down from obese. This is excellent progress! 
Typical weight loss is 50-70% of excess weight in the first year."
```

---

## 🔧 Testing the System

### **In the Flutter App:**

1. **Login** to the app
2. **Navigate** to AI Assistant screen
3. **Try these queries:**

**Without Patient ID:**
- "What vitamins do bariatric patients need?"
- "What are symptoms of dumping syndrome?"
- "How much protein should I eat after surgery?"

**With Patient ID = 1:**
- "Show me this patient's information"
- "What's their current BMI?"
- "How much weight have they lost?"

**With Patient ID = 3:**
- "Is this patient's progress on track?"
- "What's their surgery type?"
- "Should I be concerned about their status?"

---

## 📊 Sample Patients in Database

| ID | Name | Surgery Type | Months Post-Op | Weight Loss | Status |
|----|------|--------------|----------------|-------------|--------|
| 1 | John Smith | Gastric Bypass | 6 | 90 lbs | Excellent |
| 2 | Sarah Johnson | Sleeve Gastrectomy | 12 | 85 lbs | On track |
| 3 | Michael Brown | Gastric Bypass | 3 | 65 lbs | Needs counseling |
| 4 | Emily Davis | Sleeve Gastrectomy | 24 | 85 lbs | Maintenance |

---

## 🐛 Troubleshooting

### **"LLM service unavailable"**
- Make sure Ollama is running: `ollama serve`
- Check the model is pulled: `ollama list`
- Verify LLM service is on port 8001

### **"Patient not found"**
- Run the sample data script: `python scripts/create_sample_patients.py`
- Check PostgreSQL is running
- Verify patient IDs: 1, 2, 3, or 4

### **"Authorization header missing"**
- Make sure you're logged in to the Flutter app
- Token might have expired - try logging out and back in

### **AI response is slow**
- Normal! Multi-agent systems with local LLMs can take 10-30 seconds
- The supervisor needs to route, agents need to process, synthesizer needs to combine
- Watch terminal logs to see agent progress

---

## 📝 File Structure

```
llm_service/
├── app/
│   ├── main.py                      # FastAPI server
│   ├── api.py                       # Chat endpoint
│   ├── graph_medical_multiagent.py  # 🆕 Multi-agent system
│   ├── tools.py                     # Patient data retrieval tool
│   └── requirements.txt

api_gateway/
└── main_simple.py                   # 🔄 Updated with protected /chat

storage_service/
└── main_simple.py                   # 🔄 Updated with /patients endpoint

flutter_frontend/lib/
├── services/
│   └── ai_service.dart              # 🆕 AI chat service
└── screens/
    └── ai_assistant_screen.dart     # 🔄 Updated with real API

scripts/
└── create_sample_patients.py        # 🆕 Sample patient data
```

---

## 🚀 Next Steps

### **Enhance the System:**

1. **Add More Agents:**
   - Nutrition Agent (meal planning)
   - Lab Results Interpreter
   - Medication Manager

2. **Improve Tools:**
   - `get_patient_vitals(patient_id, date_range)`
   - `get_lab_results(patient_id)`
   - `get_appointment_history(patient_id)`

3. **Add Memory:**
   - Use LangGraph checkpointing for conversation history
   - Remember context across multiple messages

4. **Production Ready:**
   - Replace Ollama with cloud LLM (OpenAI, Anthropic)
   - Add proper logging and monitoring
   - Implement rate limiting
   - Add user permissions (which patients they can access)

---

## ✅ Success Indicators

You'll know the system is working when:

1. ✅ All 4 services are running (check terminal logs)
2. ✅ You can login to the Flutter app
3. ✅ AI Assistant screen loads without errors
4. ✅ Medical questions get intelligent responses (10-30 sec)
5. ✅ Patient queries return actual data from database
6. ✅ Terminal shows agent routing: Supervisor → Agents → Synthesizer

---

**Congratulations! 🎉 You now have a working multi-agent medical AI system!**
