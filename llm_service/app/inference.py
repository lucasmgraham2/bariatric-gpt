from fastapi import APIRouter

router = APIRouter()

@router.post('/generate')
def generate():
    return {"result": "LLM output"}
