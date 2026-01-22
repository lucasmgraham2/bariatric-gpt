@echo off
setlocal enabledelayedexpansion

REM Root directory of the repository
set "ROOT=%~dp0"

echo Starting Storage Service on port 8002...
start "storage_service" cmd /k "cd /d "%ROOT%storage_service" && python main_simple.py"

echo Starting API Gateway on port 8000...
start "api_gateway" cmd /k "cd /d "%ROOT%api_gateway" && python main_simple.py"

echo Starting LLM Service on port 8001...
start "llm_service" cmd /k "cd /d "%ROOT%llm_service" && python main_simple.py"

REM Flutter app will attach to the running services
echo Starting Flutter app (Chrome)...
start "flutter_frontend" cmd /k "cd /d "%ROOT%flutter_frontend" && flutter run -d chrome"

echo All services launched in separate terminals.
endlocal
