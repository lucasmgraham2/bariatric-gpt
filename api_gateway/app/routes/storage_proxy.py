from fastapi import APIRouter

router = APIRouter()

@router.get('/storage/patients')
def get_patients():
    return {"patients": []}
