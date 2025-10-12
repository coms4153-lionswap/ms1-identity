from fastapi import APIRouter, HTTPException, status
from typing import List

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=List[dict])
async def list_users():
    # Stub for Sprint 1
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not Implemented")

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(payload: dict):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not Implemented")

@router.get("/{uni}")
async def get_user(uni: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not Implemented")

@router.put("/{uni}", status_code=status.HTTP_204_NO_CONTENT)
async def replace_user(uni: str, payload: dict):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not Implemented")

@router.delete("/{uni}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(uni: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not Implemented")
