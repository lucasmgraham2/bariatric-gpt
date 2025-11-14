from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
import httpx
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

STORAGE_URL = "http://localhost:8002"
LLM_SERVICE_URL = "http://localhost:8001"
tokens = {}
# Optional key the gateway will send when persisting memory to storage service.
STORAGE_SERVICE_KEY = os.getenv("STORAGE_SERVICE_KEY")

class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    patient_id: Optional[str] = None

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
            user_data = response.json()
            # Do not expose the internal conversation memory to client-side callers.
            if isinstance(user_data, dict) and 'memory' in user_data:
                user_data = dict(user_data)  # shallow copy
                user_data.pop('memory', None)
            return user_data
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


@app.get("/auth/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    """Return the current user's profile (forwarded from storage service)."""
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
            data = response.json()
            return {"profile": data.get("profile", {})}
        except httpx.HTTPError:
            raise HTTPException(status_code=500, detail="Storage service unavailable")


@app.put("/auth/profile")
async def update_profile(payload: dict, authorization: Optional[str] = Header(None)):
    """Update the current user's profile by forwarding to storage service."""
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
            response = await client.put(f"{STORAGE_URL}/me/{user_id}/profile", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            raise HTTPException(status_code=500, detail="Storage service unavailable")

@app.post("/chat")
async def chat_with_agent(chat_data: ChatRequest, authorization: Optional[str] = Header(None)):
    """
    Protected endpoint to chat with the LLM agent graph.
    Requires authentication token and forwards user message to LLM service.
    
    Future enhancement: Auto-link patient_id from user profile/credentials
    instead of requiring it in the request.
    """
    # Extract and validate token
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # TODO: Future - fetch patient_id from user profile in storage service
    # For now, patient_id comes from request (currently null)
    llm_payload = {
        "message": chat_data.message,
        "user_id": str(user_id),
        "patient_id": chat_data.patient_id  # Will auto-link to user later
    }
    # Try to fetch the user's profile and conversation memory from the storage service and include them if available.
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{STORAGE_URL}/me/{user_id}")
            if resp.status_code == 200:
                user_info = resp.json()
                llm_payload["profile"] = user_info.get("profile", {})
            else:
                llm_payload["profile"] = {}

            # Fetch memory separately (use service key if configured)
            headers = {"X-SERVICE-KEY": STORAGE_SERVICE_KEY} if STORAGE_SERVICE_KEY else None
            if headers:
                mem_resp = await client.get(f"{STORAGE_URL}/me/{user_id}/memory", headers=headers)
            else:
                mem_resp = await client.get(f"{STORAGE_URL}/me/{user_id}/memory")

            if mem_resp.status_code == 200:
                mem_data = mem_resp.json()
                llm_payload["memory"] = mem_data.get("memory", "")
            else:
                llm_payload["memory"] = ""
            # Fetch recent conversation log (use service key if configured)
            if headers:
                log_resp = await client.get(f"{STORAGE_URL}/me/{user_id}/conversation_log", headers=headers)
            else:
                log_resp = await client.get(f"{STORAGE_URL}/me/{user_id}/conversation_log")

            if log_resp.status_code == 200:
                log_data = log_resp.json()
                llm_payload["conversation_log"] = log_data.get("log", "[]")
            else:
                llm_payload["conversation_log"] = "[]"
    except Exception:
        # If storage is unavailable or any error occurs, continue without profile/memory
        llm_payload["profile"] = {}
        llm_payload["memory"] = ""
    
    async with httpx.AsyncClient() as client:
        try:
            # Forward the request to the LLM Service
            # Use a long timeout, as agent graphs can be slow
            response = await client.post(
                f"{LLM_SERVICE_URL}/api/v1/invoke_agent_graph", 
                json=llm_payload,
                timeout=300.0 
            )
            
            # Propagate errors from the LLM service
            response.raise_for_status() 
            
            llm_result = response.json()

            # Persist updated memory if the LLM returned one
            try:
                new_memory = llm_result.get("memory")
                if new_memory:
                    async with httpx.AsyncClient() as client2:
                        headers = {"X-SERVICE-KEY": STORAGE_SERVICE_KEY} if STORAGE_SERVICE_KEY else None
                        # Only include header when configured; httpx accepts None for headers
                        if headers:
                            await client2.put(f"{STORAGE_URL}/me/{user_id}/memory", json={"memory": new_memory}, headers=headers)
                        else:
                            await client2.put(f"{STORAGE_URL}/me/{user_id}/memory", json={"memory": new_memory})

                # If the LLM returned an authoritative conversation_log, persist it directly
                # (this allows the graph to control the canonical recent-5 transcript). Otherwise,
                # fall back to the previous behavior of fetching and appending to the stored log.
                try:
                    async with httpx.AsyncClient() as client2:
                        headers = {"X-SERVICE-KEY": STORAGE_SERVICE_KEY} if STORAGE_SERVICE_KEY else None
                        llm_log = llm_result.get("conversation_log")
                        import json as _json
                        if llm_log:
                            # If the graph returned a dict, serialize it; if string, assume already serialized
                            if isinstance(llm_log, dict):
                                payload_log = _json.dumps(llm_log)
                            else:
                                payload_log = llm_log
                            if headers:
                                await client2.put(f"{STORAGE_URL}/me/{user_id}/conversation_log", json={"log": payload_log}, headers=headers)
                            else:
                                await client2.put(f"{STORAGE_URL}/me/{user_id}/conversation_log", json={"log": payload_log})
                        else:
                            # Fallback: append current exchange to stored log (legacy behavior)
                            final_resp = llm_result.get("response") or llm_result.get("final_response") or ""
                            if headers:
                                existing = await client2.get(f"{STORAGE_URL}/me/{user_id}/conversation_log", headers=headers)
                            else:
                                existing = await client2.get(f"{STORAGE_URL}/me/{user_id}/conversation_log")
                            if existing.status_code == 200:
                                log_json = existing.json().get("log", "[]")
                            else:
                                log_json = "[]"
                            try:
                                parsed = _json.loads(log_json)
                                if isinstance(parsed, dict):
                                    recent_user = parsed.get("recent_user_prompts", []) or []
                                    recent_assistant = parsed.get("recent_assistant_responses", []) or []
                                elif isinstance(parsed, list):
                                    recent_user = [e.get("text") for e in parsed if isinstance(e, dict) and e.get("role") == "user"][-5:]
                                    recent_assistant = [e.get("text") for e in parsed if isinstance(e, dict) and e.get("role") == "assistant"][-5:]
                                else:
                                    recent_user = []
                                    recent_assistant = []
                            except Exception:
                                recent_user = []
                                recent_assistant = []
                            recent_user.append(chat_data.message)
                            recent_user = recent_user[-5:]
                            recent_assistant.append(final_resp)
                            recent_assistant = recent_assistant[-5:]
                            new_log_obj = {"recent_user_prompts": recent_user, "recent_assistant_responses": recent_assistant}
                            if headers:
                                await client2.put(f"{STORAGE_URL}/me/{user_id}/conversation_log", json={"log": _json.dumps(new_log_obj)}, headers=headers)
                            else:
                                await client2.put(f"{STORAGE_URL}/me/{user_id}/conversation_log", json={"log": _json.dumps(new_log_obj)})
                except Exception:
                    pass
            except Exception:
                # Don't fail the chat if memory persistence fails - just log in server
                pass

            # Return the LLM's final response to the Flutter app
            return llm_result
        
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="LLM service is unavailable")
        except httpx.ReadTimeout:
            raise HTTPException(status_code=504, detail="Request to LLM service timed out")
        except httpx.HTTPStatusError as e:
            # Pass through the error from the downstream service if possible
            if e.response.status_code != 500:
                try:
                    return e.response.json()
                except: # Handle cases where error response isn't valid JSON
                    raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
            raise HTTPException(status_code=500, detail="An error occurred in the LLM service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)