from fastapi import APIRouter

router = APIRouter()

@router.get('/patients')
def get_patients():
    return {"patients": []}
