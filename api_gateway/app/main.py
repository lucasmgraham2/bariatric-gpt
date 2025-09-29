from fastapi import FastAPI
from app.routes import users, llm_proxy, storage_proxy

app = FastAPI()

app.include_router(users.router)
app.include_router(llm_proxy.router)
app.include_router(storage_proxy.router)
