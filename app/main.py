from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.users import users
from app.auth.auth import router as auth_router
import pathlib
from dotenv import load_dotenv
import logging
import sys
import secrets
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Load environment variables from .env file
load_dotenv()

from app.database import Base, engine

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LionSwap Identity & Accounts API",
    version="0.1.0",
    description="LionSwap User API",
)

# Add Session middleware (required for OAuth2)
# In production, get secret key from environment variable
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", secrets.token_urlsafe(32))

# Detect Cloud Run environment
is_cloud_run = os.getenv("K_SERVICE") is not None

# For Cloud Run: same_site="none" requires Secure=True (https_only=True sets this)
# This allows cookies to work with cross-site OAuth redirects
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=86400,  # 24 hours
    same_site="none" if is_cloud_run else "lax",  # Cloud Run needs 'none' for cross-site OAuth
    https_only=True if is_cloud_run else False,  # Secure flag required for same_site="none"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://storage.googleapis.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Create database tables on application startup"""
    print("=" * 50)
    print("STARTUP EVENT: Starting application initialization...")
    print("=" * 50)
    try:
        logger.info("=" * 50)
        logger.info("STARTUP EVENT: Starting database table creation...")
        logger.info(f"Database URL: {engine.url}")
        print(f"Database URL: {engine.url}")
        
        # Create all tables
        logger.info("Creating database tables...")
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Base.metadata.create_all() completed")
        print("Base.metadata.create_all() completed")
        
        # Verify table was created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Tables in database: {tables}")
        print(f"Tables in database: {tables}")
        
        if 'users' in tables or 'Users' in tables:
            logger.info("✓ Users table created successfully")
            print("✓ Users table created successfully")
        else:
            logger.warning("⚠ Users table not found after creation attempt")
            print("⚠ Users table not found after creation attempt")
            
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}", exc_info=True)
        print(f"❌ Error creating database tables: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow app to start even if DB fails
    
    print("=" * 50)
    logger.info("STARTUP EVENT: Application initialization complete")
    print("STARTUP EVENT: Application initialization complete")
    print("=" * 50)

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).parent.parent
# In Docker, files are at /app, so try that first
if pathlib.Path("/app").exists():
    OPENAPI_DIR = pathlib.Path("/app/openapi")
    STATIC_DIR = pathlib.Path("/app/static")
else:
    OPENAPI_DIR = BASE_DIR / "openapi"
    STATIC_DIR = BASE_DIR / "static"

# ------------------------------------------------------------
# Routers (Atomic + Auth)
# ------------------------------------------------------------
app.include_router(users.router)
app.include_router(auth_router)

# ------------------------------------------------------------
# Serve OpenAPI YAML (MS1)
# ------------------------------------------------------------

@app.get("/openapi/users-swagger2.yaml", include_in_schema=False)
def get_users_yaml(request: Request):
    # Try multiple possible paths
    possible_paths = [
        BASE_DIR / "openapi" / "users-swagger2.yaml",
        pathlib.Path("/app/openapi/users-swagger2.yaml"),
        pathlib.Path("openapi/users-swagger2.yaml"),
    ]
    
    yaml_path = None
    for path in possible_paths:
        if path.exists():
            yaml_path = path
            break
    
    if not yaml_path:
        logger.error(f"YAML file not found. Tried: {possible_paths}")
        logger.error(f"BASE_DIR: {BASE_DIR}, exists: {BASE_DIR.exists()}")
        if BASE_DIR.exists():
            logger.error(f"Contents of BASE_DIR: {list(BASE_DIR.iterdir())}")
        raise HTTPException(404, f"File not found. Tried: {possible_paths}")
    
    logger.info(f"Serving YAML file: {yaml_path}")
    from fastapi.responses import Response
    import re
    
    content = yaml_path.read_text(encoding="utf-8")
    
    # Dynamically change host
    current_host = request.url.hostname
    current_port = request.url.port
    current_scheme = request.url.scheme
    
    # Detect Cloud Run environment (K_SERVICE environment variable or .run.app domain)
    import os
    is_cloud_run = os.getenv("K_SERVICE") is not None or current_host.endswith(".run.app")
    
    # Change 0.0.0.0 to localhost
    if current_host == "0.0.0.0":
        current_host = "localhost"
    
    # Remove port for Cloud Run, include port for local
    if is_cloud_run:
        # Cloud Run: use host only without port, use https (port is always ignored)
        # Remove port if included in host
        if ":" in current_host:
            dynamic_host = current_host.split(":")[0]
        else:
            dynamic_host = current_host
        dynamic_scheme = "https"
    else:
        # Local environment: include port
        if current_port:
            dynamic_host = f"{current_host}:{current_port}"
        else:
            if current_scheme == "https":
                dynamic_host = current_host
            else:
                dynamic_host = f"{current_host}:8080"
        dynamic_scheme = current_scheme
    
    # Replace host line with current request's host
    content = re.sub(
        r'^host:\s*.*$',
        f'host: {dynamic_host}',
        content,
        flags=re.MULTILINE
    )
    
    # Change schemes
    if is_cloud_run:
        # Cloud Run: use https only
        content = re.sub(
            r'^schemes:\s*\n(\s*-\s*(?:https|http)\s*\n?)+',
            'schemes:\n  - https\n',
            content,
            flags=re.MULTILINE
        )
    elif current_host in ["localhost", "127.0.0.1", "0.0.0.0"]:
        # Local environment: use http only
        content = re.sub(
            r'^schemes:\s*\n(\s*-\s*(?:https|http)\s*\n?)+',
            'schemes:\n  - http\n',
            content,
            flags=re.MULTILINE
        )
    
    logger.info(f"YAML host changed to: {dynamic_host}, scheme: {dynamic_scheme}, is_cloud_run: {is_cloud_run}")
    
    return Response(
        content=content,
        media_type="text/yaml",
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/yaml; charset=utf-8"
        }
    )

# Also provide YAML files at root for compatibility
@app.get("/users-swagger2.yaml", include_in_schema=False)
def get_users_yaml_root():
    return get_users_yaml()

# ------------------------------------------------------------
# Swagger UI (custom HTML loading dropdown)
# ------------------------------------------------------------
@app.get("/swagger", response_class=HTMLResponse, include_in_schema=False)
def swagger_ui():
    html = (STATIC_DIR / "swagger.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/test-oauth", response_class=HTMLResponse, include_in_schema=False)
def test_oauth():
    """OAuth2 test page"""
    html = (STATIC_DIR / "test_oauth.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


# ------------------------------------------------------------
# Redirect root → /swagger
# ------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/swagger")

# ------------------------------------------------------------
# Static assets (Swagger HTML, JS, CSS)
# ------------------------------------------------------------
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)
