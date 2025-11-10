from fastapi import FastAPI
from .api import router
import uvicorn

app = FastAPI(
    title="LLM Service",
    description="This service runs the LangGraph multi-agent system."
)
app.include_router(router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"status": "LLM Service is running"}

if __name__ == "__main__":
    # Note: The gateway is configured for port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
