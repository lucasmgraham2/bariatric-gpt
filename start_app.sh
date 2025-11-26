#!/bin/bash

# Function to open a new terminal window and run a command
open_window() {
    local title="$1"
    local command="$2"
    # Escape double quotes in the command for AppleScript
    local escaped_command="${command//\"/\\\"}"
    
    # Use AppleScript to tell Terminal to do script.
    osascript -e "tell application \"Terminal\" to do script \"$escaped_command\""
}

# Get the absolute path of the project root
PROJECT_ROOT=$(pwd)

echo "Starting Bariatric GPT Services..."

# 1. Storage Service
echo "Launching Storage Service (Port 8002)..."
open_window "Storage Service" "cd \"$PROJECT_ROOT\" && python storage_service/main_simple.py"

# 2. LLM Service
echo "Launching LLM Service (Port 8001)..."
open_window "LLM Service" "cd \"$PROJECT_ROOT/llm_service\" && python -m app.main"

# 3. API Gateway
echo "Launching API Gateway (Port 8000)..."
open_window "API Gateway" "cd \"$PROJECT_ROOT\" && python api_gateway/main_simple.py"

# 4. Flutter Frontend
echo "Launching Flutter Frontend..."
open_window "Flutter Frontend" "cd \"$PROJECT_ROOT/flutter_frontend\" && flutter run"

echo "All services launched in separate terminal windows."
