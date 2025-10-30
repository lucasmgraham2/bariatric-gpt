@echo off
echo.
echo ========================================
echo Restarting LLM Service with Faster Model
echo ========================================
echo.
echo Press Ctrl+C in the LLM service terminal to stop it
echo Then run this command:
echo.
echo cd llm_service
echo uvicorn app.main:app --host 0.0.0.0 --port 8001
echo.
pause
