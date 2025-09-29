from fastapi import FastAPI
from app.api import patients

app = FastAPI()
app.include_router(patients.router)
