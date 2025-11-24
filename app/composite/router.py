from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.composite.service import delete_user_and_items
import json

router = APIRouter(prefix="/composite", tags=["composite"])

@router.delete("/users/{uni}")
def composite_delete_user(uni: str):
    """
    Delete a user and all their listed items (ms1 + ms2)
    
    This composite service:
    - Checks if user exists (logical foreign key constraint)
    - Validates that user has no active reservations/sales
    - Deletes user's items from ms2-catalog (parallel execution)
    - Deletes user from ms1-identity (parallel execution)
    
    Returns:
    - 200: Both deletions successful
    - 207: Partial success (one service failed)
    - 404: User not found
    - 409: Conflict (blocked items prevent deletion)
    """
    status_code, body = delete_user_and_items(uni)
    
    if status_code == 404:
        raise HTTPException(status_code=404, detail=body.get("error", "User not found"))
    elif status_code == 409:
        raise HTTPException(status_code=409, detail=body)
    
    return JSONResponse(
        content=body,
        status_code=status_code
    )
