"""
Run the LLM service directly.

Usage:
    python main_simple.py

This file mirrors the simple runners used by the other services in this repo
(storage and gateway). By default it runs on port 8001 (the gateway expects
this), but you can override using the `PORT` environment variable.
"""

import os
import uvicorn

# Import the FastAPI app defined in app/main.py
try:
    from app.main import app
except Exception:
    # If package import fails (e.g. running from a different cwd), try relative import
    from .app.main import app  # type: ignore

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting LLM service on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
