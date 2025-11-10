from fastapi import APIRouter, HTTPException, status, Response
from typing import List, Dict, Any
from datetime import datetime
from threading import RLock

router = APIRouter(prefix="/users", tags=["users"])

# In-memory store (keyed by UNI). This resets on app restart.
_USERS: Dict[str, Dict[str, Any]] = {}
_LOCK = RLock()

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def require_fields(data: Dict[str, Any], fields: list[str]):
    missing = [f for f in fields if f not in data or data[f] in (None, "")]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field(s): {', '.join(missing)}"
        )

@router.get("", response_model=List[dict])
async def list_users():
    with _LOCK:
        return list(_USERS.values())

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(payload: dict, response: Response):
    # Required by your Swagger: uni, student_name, email
    require_fields(payload, ["uni", "student_name", "email"])
    uni = payload["uni"]

    with _LOCK:
        if uni in _USERS:
            # Already exists
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user = {
            "uni": uni,
            "student_name": payload.get("student_name"),
            "major": payload.get("major"),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        _USERS[uni] = user

    # Set Location header per your Swagger 201 response
    response.headers["Location"] = f"/users/{uni}"
    return user

@router.get("/{uni}")
async def get_user(uni: str):
    with _LOCK:
        user = _USERS.get(uni)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

@router.put("/{uni}", status_code=status.HTTP_200_OK)
async def replace_user(uni: str, payload: dict):
    allowed = {"student_name", "major", "phone"}
    with _LOCK:
        user = _USERS.get(uni)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        for k in allowed:
            if k in payload:
                user[k] = payload[k]
        user["updated_at"] = now_iso()
        _USERS[uni] = user
        return user  # <-- return updated JSON

@router.delete("/{uni}", status_code=status.HTTP_200_OK)
async def delete_user(uni: str):
    with _LOCK:
        if uni not in _USERS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        _USERS.pop(uni, None)
    return {"message": f'Successfully deleted {uni} user'}
