from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
import httpx

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

STORAGE_URL = "http://localhost:8002"
tokens = {}

class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@app.post("/auth/register")
async def register(user_data: UserRegister):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{STORAGE_URL}/register", json=user_data.model_dump())
            if response.status_code == 400:
                raise HTTPException(status_code=400, detail=response.json().get("detail"))
            response.raise_for_status()
            user = response.json()
            token = f"token_{uuid.uuid4().hex[:16]}"
            tokens[token] = user["id"]
            return {"access_token": token, "token_type": "bearer", "user_id": user["id"]}
        except httpx.HTTPError:
            raise HTTPException(status_code=500, detail="Storage service unavailable")

@app.post("/auth/login") 
async def login(login_data: UserLogin):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{STORAGE_URL}/login", json=login_data.model_dump())
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            response.raise_for_status()
            result = response.json()
            token = f"token_{uuid.uuid4().hex[:16]}"
            tokens[token] = result["user_id"]
            return {"access_token": token, "token_type": "bearer", "user_id": result["user_id"]}
        except httpx.HTTPError:
            raise HTTPException(status_code=500, detail="Storage service unavailable")

@app.get("/auth/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{STORAGE_URL}/me/{user_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            raise HTTPException(status_code=500, detail="Storage service unavailable")

@app.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        token = authorization.split(" ")[1]
        if token in tokens:
            del tokens[token]
    except IndexError:
        pass
    
    return {"message": "Logout successful"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)