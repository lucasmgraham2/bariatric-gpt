# Bariatric GPT

A simplified medical application with authentication and Flutter frontend.

## Quick Setup

### 1. Database Setup

**Windows:**
```bash
setup_windows_postgres.bat
```

**macOS:**
```bash
chmod +x setup_macos_postgres.sh
./setup_macos_postgres.sh
```

**What this creates:**
- Database: `bariatric_db`
- User: `bariatric_user`
- Password: `bariatric_password`
- Host: `localhost`
- Port: `5432`

### 2. Start Services
```bash
# Terminal 1 - Storage Service (Port 8002)
python storage_service/main_simple.py

# Terminal 2 - API Gateway (Port 8000)  
python api_gateway/main_simple.py

# Terminal 3 - Flutter App
cd flutter_frontend
flutter run

# Terminal 4 - LLM Serivce
uvicorn llm_service.app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 3. Test the Setup
Create sample users (optional):
```bash
python scripts/create_sample_data.py
```

## Architecture

- **Storage Service**: User authentication and patient data management (PostgreSQL)
- **API Gateway**: API orchestration, token management, and chat routing
- **LLM Service**: Multi-agent AI system with medical expertise (Port 8001)
- **Flutter Frontend**: Mobile application with authentication and AI chat

### NEW: Multi-Agent AI System
The app now includes an intelligent medical assistant that uses multiple specialized agents:
- **Supervisor**: Routes queries to appropriate specialists
- **Medical Agent**: Answers medical questions and provides guidance
- **Data Agent**: Retrieves patient information from database
- **Synthesizer**: Combines responses into coherent answers

See **[MULTI_AGENT_SETUP.md](MULTI_AGENT_SETUP.md)** for complete setup and usage guide.

## API Endpoints

- `POST /auth/register` - Create new user account
- `POST /auth/login` - User authentication
- `GET /auth/me` - Get current user profile
- `POST /auth/logout` - User logout

## Requirements

- **Python 3.7+** with pip
- **PostgreSQL 14+** (auto-installed by setup scripts)
- **Flutter SDK** for mobile development

## Troubleshooting

**Database Connection Issues:**
- Ensure PostgreSQL service is running
- Check credentials match: `bariatric_user` / `bariatric_password`

**Port Conflicts:**
- Storage Service: Port 8002
- API Gateway: Port 8000
- Make sure these ports are available

## Team Development

See `TEAM_DATABASE_SETUP.md` for detailed setup instructions and team collaboration guidelines.
