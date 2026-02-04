# Bariatric GPT

AI-powered bariatric care assistant with multi-agent medical expertise, user authentication, and Flutter mobile app.

## Prerequisites

**Required Downloads:**
1. **Python 3.9+** - [Download here](https://www.python.org/downloads/)
2. **Flutter SDK** - [Download here](https://docs.flutter.dev/get-started/install)
3. **Ollama** - [Download here](https://ollama.com/download)
4. **PostgreSQL 14+** - [Download here](https://www.postgresql.org/download/) (or use auto-setup)

## Quick Setup

### 1. Install Ollama Model
```powershell
# Download the LLM model (required for AI features)
ollama pull deepseek-r1:8b
```

### 2. Setup Database

**Windows:**
```powershell
.\setup_windows_postgres.bat
```

**macOS/Linux:**
```bash
chmod +x setup_macos_postgres.sh
./setup_macos_postgres.sh
```

This creates:
- Database: `bariatric_db`
- User: `bariatric_user`
- Password: `bariatric_password`
- Port: `5432`

### 3. Install Python Dependencies
```powershell
# Install for all services
pip install -r api_gateway/requirements.txt
pip install -r storage_service/requirements.txt
pip install -r llm_service/requirements.txt
```

### 4. Install Flutter Dependencies
```powershell
cd flutter_frontend
flutter pub get
```

### 5. Start All Services

**Easiest Option (Windows):**
```powershell
.\run_all_services.bat
```

**Manual Option (Any OS):**
```powershell
# Terminal 1 - Storage Service (Port 8002)
python storage_service/main_simple.py

# Terminal 2 - API Gateway (Port 8000)
python api_gateway/main_simple.py

# Terminal 3 - LLM Service (Port 8001)
cd llm_service
python main_simple.py

# Terminal 4 - Flutter App
cd flutter_frontend
flutter run -d chrome
```

## Architecture

```
Flutter App → API Gateway (8000) → Storage Service (8002) [PostgreSQL]
                    ↓
              LLM Service (8001) [Ollama + LangGraph]
```

**Components:**
- **Storage Service**: PostgreSQL-backed user auth and patient data
- **API Gateway**: Request routing, token management, context assembly
- **LLM Service**: Multi-agent AI system with RAG knowledge retrieval
- **Flutter Frontend**: Cross-platform mobile/web UI

## Features

- User authentication and profile management
- AI chat with medical expertise (bariatric surgery focus)
- Patient data management and meal logging
- Knowledge retrieval from medical documents (RAG)
- Allergen-aware meal suggestions
- Conversation memory and context tracking

## Optional: Sample Data
```powershell
python scripts/create_sample_data.py
python scripts/create_sample_patients.py
```

## Troubleshooting

**Ollama Model Not Found:**
```powershell
ollama pull deepseek-r1:8b
```

**Database Connection Failed:**
- Ensure PostgreSQL is running
- Verify credentials: `bariatric_user` / `bariatric_password`

**Port Already in Use:**
- Check ports 8000, 8001, 8002 are available
- Kill conflicting processes or modify port configs

## Documentation

- [Team Setup Guide](TEAM_DATABASE_SETUP.md) - Team collaboration and database setup
- [Profile Integration](PROFILE_INTEGRATION_GUIDE.md) - Linking patient profiles to users
