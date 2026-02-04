#!/bin/bash
echo "🛑 Stopping any running services..."
pkill -f "uvicorn" || true

echo "🧹 Deleting and Rebuilding Knowledge Base..."
cd "$(dirname "$0")" # Ensure we are in project root
python llm_service/app/build_knowledge.py

echo "✅ Database rebuilt."
echo "👉 You can now run ./start_app.sh"
