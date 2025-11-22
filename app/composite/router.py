from fastapi import APIRouter, Response
from app.composite.service import delete_user_and_items

router = APIRouter(prefix="/composite", tags=["composite"])

@router.delete("/users/{uni}")
def composite_delete_user(uni: str):
    status_code, body = delete_user_and_items(uni)
    return Response(
        content=None if body is None else __import__("json").dumps(body),
        media_type="application/json",
        status_code=status_code
    )
