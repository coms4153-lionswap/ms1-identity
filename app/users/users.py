from fastapi import APIRouter, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user_model import User
from app.database import SessionLocal
from uuid import uuid4
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
import time

router = APIRouter(prefix="/users", tags=["users"])

# ---- Async operation store (unchanged) ----
_OPS = {}
_EXEC = ThreadPoolExecutor(max_workers=2)
_LOCK = RLock()

# ---- Helpers ----

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_fields(data, fields):
    missing = [f for f in fields if f not in data or not data[f]]
    if missing:
        raise HTTPException(400, f"Missing: {', '.join(missing)}")

def etag_of(user: User) -> str:
    return f'W/"{user.version}"'

# ---- CRUD API ----

@router.get("", response_model=list[dict])
async def list_users():
    with SessionLocal() as db:
        users = db.query(User).all()
        return [
            {
                "uni": u.uni,
                "student_name": u.student_name,
                "dept_name": u.dept_name,
                "email": u.email,
                "phone": u.phone,
                "avatar_url": u.avatar_url,
                "credibility_score": float(u.credibility_score or 0),
                "last_seen_at": u.last_seen_at,
                "created_at": u.created_at,
                "updated_at": u.updated_at,
                "version": u.version,
            }
            for u in users
        ]

@router.post("", status_code=201)
async def create_user(payload: dict, response: Response):
    require_fields(payload, ["uni", "student_name", "email"])
    uni = payload["uni"]

    with SessionLocal() as db:
        # check duplicate
        if db.query(User).filter(User.uni == uni).first():
            raise HTTPException(409, "User already exists")

        user = User(
            uni=uni,
            student_name=payload["student_name"],
            dept_name=payload.get("dept_name"),
            email=payload["email"],
            phone=payload.get("phone"),
            avatar_url=payload.get("avatar_url"),
            credibility_score=0.00,
            last_seen_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            version=1,
        )

        db.add(user)
        db.commit()

        response.headers["Location"] = f"/users/{uni}"

        return {
            "uni": user.uni,
            "student_name": user.student_name,
            "email": user.email,
            "phone": user.phone,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "version": user.version,
        }

@router.get("/{uni}")
async def get_user(uni: str, request: Request):
    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()
        if not user:
            raise HTTPException(404, "User not found")

        tag = etag_of(user)

        # ETag returns 304 Not Modified
        if request.headers.get("If-None-Match") == tag:
            return Response(status_code=304, headers={"ETag": tag})

        resp = JSONResponse({
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "credibility_score": float(user.credibility_score or 0),
            "last_seen_at": user.last_seen_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "version": user.version,
        })
        resp.headers["ETag"] = tag
        return resp

@router.put("/{uni}", status_code=200)
async def replace_user(uni: str, payload: dict, request: Request):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HTTPException(428, "If-Match required")

    allowed = {"student_name", "dept_name", "phone"}

    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()
        if not user:
            raise HTTPException(404, "User not found")

        current_etag = etag_of(user)
        if if_match != current_etag:
            raise HTTPException(412, "ETag mismatch")

        # Update fields
        for f in allowed:
            if f in payload:
                setattr(user, f, payload[f])

        # Version bump
        user.version += 1
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        new_etag = etag_of(user)

        resp = JSONResponse({
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "email": user.email,
            "phone": user.phone,
            "updated_at": user.updated_at,
            "version": user.version,
        })
        resp.headers["ETag"] = new_etag
        return resp

@router.delete("/{uni}")
async def delete_user(uni: str):
    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()
        if not user:
            raise HTTPException(404, "User not found")

        db.delete(user)
        db.commit()

        return {"message": f'Successfully deleted "{uni}" user'}

# ---- Async export (still using DB, not in-memory) ----

def _run_export(op_id: str, uni: str):
    _OPS[op_id] = {"status": "running"}
    time.sleep(2)

    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()

    if user:
        _OPS[op_id] = {
            "status": "succeeded",
            "result": {"uri": f"/users/{uni}"}
        }
    else:
        _OPS[op_id] = {
            "status": "failed",
            "result": {"error": "User not found"}
        }

@router.post("/{uni}/export", status_code=202)
async def start_export(uni: str):
    op_id = uuid4().hex
    _OPS[op_id] = {"status": "pending"}
    _EXEC.submit(_run_export, op_id, uni)
    return {
        "operation_id": op_id,
        "_links": {"self": {"href": f"/operations/{op_id}"}}
    }
