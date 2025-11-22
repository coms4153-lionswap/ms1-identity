from fastapi import APIRouter, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from datetime import datetime
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import time

router = APIRouter(prefix="/users", tags=["users"])

_USERS: Dict[str, Dict[str, Any]] = {}
_LOCK = RLock()

# simple in-process async ops for demo
_EXEC = ThreadPoolExecutor(max_workers=2)
_OPS: Dict[str, Dict[str, Any]] = {}  # op_id -> {status, result}

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def require_fields(data: Dict[str, Any], fields: list[str]):
    missing = [f for f in fields if f not in data or data[f] in (None, "")]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing: {', '.join(missing)}")

def etag_of(user: Dict[str, Any]) -> str:
    return f'W/"{user.get("version", 1)}"'

def bump_version(user: Dict[str, Any]) -> None:
    user["version"] = int(user.get("version", 1)) + 1
    user["updated_at"] = now_iso()

@router.get("", response_model=List[dict])
async def list_users():
    with _LOCK:
        return list(_USERS.values())

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(payload: dict, response: Response):
    require_fields(payload, ["uni", "student_name", "email"])
    uni = payload["uni"]
    with _LOCK:
        if uni in _USERS:
            raise HTTPException(409, "User already exists")
        user = {
            "uni": uni,
            "student_name": payload.get("student_name"),
            "major": payload.get("major"),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "version": 1,  # for ETag
        }
        _USERS[uni] = user
    response.headers["Location"] = f"/users/{uni}"
    return user

@router.get("/{uni}")
async def get_user(uni: str, request: Request):
    with _LOCK:
        user = _USERS.get(uni)
        if not user:
            raise HTTPException(404, "User not found")
        tag = etag_of(user)

    # If-None-Match → 304
    if request.headers.get("If-None-Match") == tag:
        return Response(status_code=304, headers={"ETag": tag})

    resp = JSONResponse(user)
    resp.headers["ETag"] = tag
    return resp

@router.put("/{uni}", status_code=status.HTTP_200_OK)
async def replace_user(uni: str, payload: dict, request: Request):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HTTPException(428, "If-Match required")

    allowed = {"student_name", "major", "phone"}
    with _LOCK:
        user = _USERS.get(uni)
        if not user:
            raise HTTPException(404, "User not found")
        current = etag_of(user)
        if if_match != current:
            raise HTTPException(412, "ETag mismatch")
        for k in allowed:
            if k in payload:
                user[k] = payload[k]
        bump_version(user)
        _USERS[uni] = user
        tag = etag_of(user)

    resp = JSONResponse(user)
    resp.headers["ETag"] = tag
    return resp

@router.delete("/{uni}", status_code=status.HTTP_200_OK)
async def delete_user(uni: str):
    with _LOCK:
        if uni not in _USERS:
            raise HTTPException(404, "User not found")
        _USERS.pop(uni, None)
    return {"message": f'Successfully deleted "{uni}" user'}

# ---- 202 async export + polling ----

def _run_export(op_id: str, uni: str):
    _OPS[op_id] = {"status": "running"}
    time.sleep(2)  # simulate work
    with _LOCK:
        u = _USERS.get(uni)
    if u:
        _OPS[op_id] = {"status": "succeeded", "result": {"uri": f"/users/{uni}"}}
    else:
        _OPS[op_id] = {"status": "failed", "result": {"error": "User not found"}}

@router.post("/{uni}/export", status_code=status.HTTP_202_ACCEPTED)
async def start_export(uni: str):
    op_id = uuid4().hex
    _OPS[op_id] = {"status": "pending"}
    _EXEC.submit(_run_export, op_id, uni)
    return {
        "operation_id": op_id,
        "_links": {"self": {"href": f"/operations/{op_id}"}}
    }
