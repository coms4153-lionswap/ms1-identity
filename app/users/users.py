from fastapi import APIRouter, HTTPException, status, Response, Request, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user_model import User
from app.database import SessionLocal
from datetime import datetime
import re

router = APIRouter(prefix="/users", tags=["users"])

class UserCreate(BaseModel):
    uni: str
    student_name: str
    email: EmailStr
    dept_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    student_name: Optional[str] = None
    dept_name: Optional[str] = None
        phone: Optional[str] = None

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
    timestamp = user.last_seen_at.isoformat() if user.last_seen_at else "0"
    return f'W/"{timestamp}"'

def normalize_etag(etag: str) -> str:
    if not etag:
        return ""
    
    etag = etag.strip()
    
    if etag.startswith('W/'):
        value = etag[2:].strip()
        value = value.strip('"').strip("'")
        return f'W/{value}'
    else:
        value = etag.strip('"').strip("'")
        return value

def build_links(uni: str, request: Request) -> dict:
    base_url = str(request.base_url).rstrip('/')
    return {
        "self": {"href": f"/users/{uni}"},
        "profile": {"href": f"/users/{uni}/profile"},
        "update": {"href": f"/users/{uni}", "method": "PUT"},
        "delete": {"href": f"/users/{uni}", "method": "DELETE"},
    }

@router.get("", response_model=list[dict])
async def list_users(request: Request):
    with SessionLocal() as db:
        users = db.query(User).all()
        return [
            {
                "user_id": u.user_id,
                "uni": u.uni,
                "student_name": u.student_name,
                "dept_name": u.dept_name,
                "email": u.email,
                "phone": u.phone,
                "avatar_url": u.avatar_url,
                "credibility_score": float(u.credibility_score or 0),
                "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
                "_links": build_links(u.uni, request),
            }
            for u in users
        ]

@router.post("", status_code=201)
async def create_user(payload: UserCreate, response: Response, request: Request):
    with SessionLocal() as db:
        if db.query(User).filter(User.uni == payload.uni).first():
            raise HTTPException(409, "User already exists")

        user = User(
            uni=payload.uni,
            student_name=payload.student_name,
            dept_name=payload.dept_name,
            email=payload.email,
            phone=payload.phone,
            avatar_url=payload.avatar_url,
            credibility_score=0.00,
            last_seen_at=None,
        )

        db.add(user)
        db.commit()

        response.headers["Location"] = f"/users/{user.uni}"

        return {
            "user_id": user.user_id,
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "credibility_score": float(user.credibility_score or 0),
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
            "_links": build_links(user.uni, request),
        }

@router.get("/by-email/{email}")
async def get_user_by_email(email: str = Path(..., description="User email address", pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')):
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(
            status_code=400, 
            detail="Invalid email format. This endpoint only accepts email addresses (e.g., user@example.com)."
        )
    
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(404, "User not found")
        
        return {
            "user_id": user.user_id
        }

@router.get("/by-id/{user_id}")
async def get_user_by_id(user_id: int, request: Request):
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")

        tag = etag_of(user)

        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and normalize_etag(if_none_match) == normalize_etag(tag):
            return Response(status_code=304, headers={"ETag": tag})

        resp = JSONResponse({
            "user_id": user.user_id,
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "credibility_score": float(user.credibility_score or 0),
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
            "_links": build_links(user.uni, request),
        })
        resp.headers["ETag"] = tag
        return resp

@router.get("/{uni}")
async def get_user(uni: str, request: Request):
    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()
        if not user:
            raise HTTPException(404, "User not found")

        tag = etag_of(user)

        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and normalize_etag(if_none_match) == normalize_etag(tag):
            return Response(status_code=304, headers={"ETag": tag})

        resp = JSONResponse({
            "user_id": user.user_id,
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "credibility_score": float(user.credibility_score or 0),
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
            "_links": build_links(user.uni, request),
        })
        resp.headers["ETag"] = tag
        return resp

@router.put("/{uni}", status_code=200)
async def replace_user(uni: str, payload: UserUpdate, request: Request):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HTTPException(428, "If-Match required")

    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()
        if not user:
            raise HTTPException(404, "User not found")

        current_etag = etag_of(user)
        if normalize_etag(if_match) != normalize_etag(current_etag):
            raise HTTPException(412, "ETag mismatch")

        if payload.student_name is not None:
            user.student_name = payload.student_name
        if payload.dept_name is not None:
            user.dept_name = payload.dept_name
        if payload.phone is not None:
            user.phone = payload.phone

        user.last_seen_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        new_etag = etag_of(user)

        resp = JSONResponse({
            "user_id": user.user_id,
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "credibility_score": float(user.credibility_score or 0),
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
            "_links": build_links(user.uni, request),
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

@router.get("/{uni}/profile")
async def get_user_profile(uni: str, request: Request):
    with SessionLocal() as db:
        user = db.query(User).filter(User.uni == uni).first()
        if not user:
            raise HTTPException(404, "User not found")

        tag = etag_of(user)

        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and normalize_etag(if_none_match) == normalize_etag(tag):
            return Response(status_code=304, headers={"ETag": tag})

        profile_data = {
            "uni": user.uni,
            "student_name": user.student_name,
            "dept_name": user.dept_name,
            "avatar_url": user.avatar_url,
            "credibility_score": float(user.credibility_score or 0),
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
            "_links": {
                "self": {"href": f"/users/{uni}/profile"},
                "user": {"href": f"/users/{uni}"},
                "update": {"href": f"/users/{uni}", "method": "PUT"},
            }
        }

        resp = JSONResponse(profile_data)
        resp.headers["ETag"] = tag
        return resp

