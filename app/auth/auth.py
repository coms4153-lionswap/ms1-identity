from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.config import Config
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import SessionLocal
from app.models.user_model import User
from app.auth_config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_DISCOVERY_URL,
    JWT_SERVICE_URL,
    FRONTEND_URL,
    get_redirect_uri,
)
import logging
import httpx
import os
import secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Session store (for testing without JWT service)
session_store = {}  # {session_id: user_id}

# OAuth configuration
config = Config(environ={
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID or "",
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET or "",
})

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url=GOOGLE_DISCOVERY_URL,
    client_kwargs={
        "scope": "openid email profile"
    }
)


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_user_from_google(db: Session, google_user_info: dict) -> User:
    """Get or create user from Google user information"""
    google_id = google_user_info.get("sub")
    email = google_user_info.get("email")
    name = google_user_info.get("name", "")
    picture = google_user_info.get("picture")
    
    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to retrieve required information from Google."
        )
    
    # Find existing user by google_id
    user = db.query(User).filter(User.google_id == google_id).first()
    
    if user:
        # Update existing user information (name, avatar, etc.)
        if name and not user.student_name:
            user.student_name = name
        if picture and not user.avatar_url:
            user.avatar_url = picture
        if email and user.email != email:
            user.email = email
        user.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    
    # Find existing user by email (if google_id is not present)
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Link google_id to existing user
        user.google_id = google_id
        if name and not user.student_name:
            user.student_name = name
        if picture and not user.avatar_url:
            user.avatar_url = picture
        user.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    
    # Create new user
    # uni is the part before @ in email or auto-generated
    uni = email.split("@")[0] if "@" in email else f"user_{google_id[:8]}"
    
    # Check for uni duplicates and handle
    base_uni = uni
    counter = 1
    while db.query(User).filter(User.uni == uni).first():
        uni = f"{base_uni}_{counter}"
        counter += 1
    
    user = User(
        uni=uni,
        student_name=name or email.split("@")[0],
        email=email,
        avatar_url=picture,
        google_id=google_id,
        credibility_score=0.00,
        last_seen_at=datetime.utcnow(),
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"New user created: {user.uni} (Google ID: {google_id})")
    return user


@router.get("/google/login")
async def google_login(request: Request):
    """Start Google OAuth2 login"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth2 configuration is incomplete. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    
    # Get base URL and force HTTPS for Cloud Run
    base_url = str(request.base_url)
    # Check if we're on Cloud Run (always use HTTPS)
    is_cloud_run = os.getenv('K_SERVICE') is not None or '.run.app' in base_url
    if is_cloud_run:
        # Force HTTPS for Cloud Run
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://', 1)
        elif not base_url.startswith('https://'):
            # If no scheme, add https
            base_url = f"https://{base_url.lstrip('/')}"
    
    redirect_uri = get_redirect_uri(base_url)
    
    # Debug logging
    logger.info(f"OAuth login - base_url: {base_url}, redirect_uri: {redirect_uri}, is_cloud_run: {is_cloud_run}")
    logger.info(f"Session exists: {hasattr(request, 'session')}, Session keys: {list(request.session.keys()) if hasattr(request, 'session') else 'N/A'}")
    
    try:
        return await oauth.google.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(f"Google login redirect error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during login redirect: {str(e)}"
        )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth2 callback"""
    # Debug logging
    logger.info(f"OAuth callback - Session exists: {hasattr(request, 'session')}, Session keys: {list(request.session.keys()) if hasattr(request, 'session') else 'N/A'}")
    logger.info(f"Query params: {dict(request.query_params)}")
    
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.error(f"OAuth error: {e}", exc_info=True)
        logger.error(f"Session state: {request.session.get('_state', 'NOT_FOUND') if hasattr(request, 'session') else 'NO_SESSION'}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )
    
    # Get user information
    user_info = token.get("userinfo")
    if not user_info:
        # If userinfo is not available, fetch from userinfo endpoint
        try:
            resp = await oauth.google.get("https://www.googleapis.com/oauth2/v2/userinfo", token=token)
            user_info = resp.json()
        except Exception as e:
            logger.error(f"Error fetching user information: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to retrieve user information."
            )
    
    # Get or create user
    # In production, database is required, so handle errors appropriately
    try:
        user = get_or_create_user_from_google(db, user_info)
    except Exception as e:
        logger.error(f"Database error: {e}", exc_info=True)
        # Detect production environment
        is_production = os.getenv("ENVIRONMENT") == "production" or os.getenv("K_SERVICE") is not None
        
        if is_production:
            # In production, return 500 error on database failure
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error occurred. Please contact administrator."
            )
        else:
            # In development, redirect to frontend with error info (for testing)
            google_id = user_info.get("sub", "unknown")
            email = user_info.get("email", "unknown@example.com")
            name = user_info.get("name", email.split("@")[0])
            google_access_token = token.get("access_token")
            google_id_token = token.get("id_token")
            uni = email.split("@")[0] if "@" in email else "user_unknown"
            
            # Redirect to frontend homepage (no query parameters)
            frontend_url = request.query_params.get("state") or FRONTEND_URL
            if not frontend_url.startswith("http"):
                frontend_url = FRONTEND_URL
            
            # Simple redirect to homepage without parameters
            redirect_url = f"{FRONTEND_URL}#access_token={token['access_token']}&id_token={token.get('id_token', '')}&email={user_info['email']}&user_id={user.id}"
            return RedirectResponse(url=redirect_url)
    
    # Extract Google access_token (to pass to JWT service)
    google_access_token = token.get("access_token")
    google_id_token = token.get("id_token")  # OIDC id_token (optional)
    
    # Generate session ID (for testing without JWT service)
    session_id = secrets.token_urlsafe(32)
    session_store[session_id] = user.user_id
    
    # Redirect to frontend homepage (no query parameters)
    # Use state parameter if provided, otherwise use FRONTEND_URL from environment
    frontend_url = request.query_params.get("state") or FRONTEND_URL
    
    # Ensure frontend_url is a valid URL
    if not frontend_url.startswith("http"):
        # If state doesn't contain URL, use FRONTEND_URL
        frontend_url = FRONTEND_URL
    
    # Simple redirect to homepage without parameters
    response = RedirectResponse(url=frontend_url)
    
    # Set session cookie (for testing without JWT service)
    # In production, set secure=True
    is_production = os.getenv("ENVIRONMENT") == "production" or os.getenv("K_SERVICE") is not None
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=is_production,  # Force HTTPS in production only
        max_age=86400  # 24 hours
    )
    
    return response


@router.get("/me")
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get current user information
    Authentication via JWT token or session cookie (can test without JWT service)
    """
    user_id = None
    
    # 1. Try authentication with JWT token (issued by another microservice)
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        
        # Request token verification from JWT service
        try:
            async with httpx.AsyncClient() as client:
                verify_response = await client.post(
                    f"{JWT_SERVICE_URL}/auth/verify",
                    json={"token": token},
                    timeout=5.0
                )
                
                if verify_response.status_code == 200:
                    verify_data = verify_response.json()
                    if verify_data.get("valid", False):
                        payload = verify_data.get("payload", {})
                        user_id = payload.get("sub") or payload.get("user_id")
        
        except httpx.RequestError as e:
            logger.warning(f"JWT service connection failed (test mode): {e}")
            # Fallback to session if JWT service is unavailable
            pass
    
    # 2. Try authentication with session cookie (for testing without JWT service)
    if not user_id:
        session_id = request.cookies.get("session_id")
        if session_id:
            user_id = session_store.get(session_id)
    
    # Authentication failed
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. JWT token (Authorization: Bearer <token>) or OAuth2 login is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user information
    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
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
        "google_id": user.google_id,
    }


@router.post("/verify-jwt")
async def verify_jwt_token(request: Request):
    """
    Verify JWT token (from another microservice)
    This endpoint proxies to JWT service
    Returns 503 error if JWT service is unavailable
    """
    data = await request.json()
    token = data.get("token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token not provided."
        )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{JWT_SERVICE_URL}/auth/verify",
                json={"token": token},
                timeout=5.0
            )
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"JWT service connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to JWT service. Please check if JWT service is running."
        )


@router.post("/logout")
async def logout(request: Request):
    """Logout (remove session)"""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in session_store:
        del session_store[session_id]
    
    response = JSONResponse({"message": "Logged out successfully."})
    response.delete_cookie("session_id")
    return response

