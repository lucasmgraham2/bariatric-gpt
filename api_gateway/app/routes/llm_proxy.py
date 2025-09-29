from fastapi import APIRouter

router = APIRouter()

@router.post('/llm/generate')
def generate_text():
    return {"result": "Generated text"}
