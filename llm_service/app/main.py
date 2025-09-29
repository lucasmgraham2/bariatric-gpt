from fastapi import FastAPI
from app import inference

app = FastAPI()
app.include_router(inference.router)
