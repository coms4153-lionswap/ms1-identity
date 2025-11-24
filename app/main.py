from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.users import users
from app.composite import router as composite_router
import pathlib
from dotenv import load_dotenv
import logging
import sys

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

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "Location", "Content-Type"],  # ETag를 클라이언트에서 접근 가능하도록
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
# Routers (Atomic + Composite)
# ------------------------------------------------------------
app.include_router(users.router)
app.include_router(composite_router.router)

# ------------------------------------------------------------
# Serve OpenAPI YAML (MS1 + Composite)
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
    
    # 동적으로 host 변경
    current_host = request.url.hostname
    current_port = request.url.port
    current_scheme = request.url.scheme
    
    # Cloud Run 환경 감지 (K_SERVICE 환경 변수 또는 .run.app 도메인)
    import os
    is_cloud_run = os.getenv("K_SERVICE") is not None or current_host.endswith(".run.app")
    
    # 0.0.0.0을 localhost로 변경
    if current_host == "0.0.0.0":
        current_host = "localhost"
    
    # Cloud Run이면 포트 제거, 로컬이면 포트 포함
    if is_cloud_run:
        # Cloud Run: 포트 없이 host만 사용, https 사용 (포트는 항상 무시)
        # host에서 포트가 포함되어 있으면 제거
        if ":" in current_host:
            dynamic_host = current_host.split(":")[0]
        else:
            dynamic_host = current_host
        dynamic_scheme = "https"
    else:
        # 로컬 환경: 포트 포함
        if current_port:
            dynamic_host = f"{current_host}:{current_port}"
        else:
            if current_scheme == "https":
                dynamic_host = current_host
            else:
                dynamic_host = f"{current_host}:8080"
        dynamic_scheme = current_scheme
    
    # host 라인을 현재 요청의 host로 교체
    content = re.sub(
        r'^host:\s*.*$',
        f'host: {dynamic_host}',
        content,
        flags=re.MULTILINE
    )
    
    # schemes 변경
    if is_cloud_run:
        # Cloud Run: https만 사용
        content = re.sub(
            r'^schemes:\s*\n(\s*-\s*(?:https|http)\s*\n?)+',
            'schemes:\n  - https\n',
            content,
            flags=re.MULTILINE
        )
    elif current_host in ["localhost", "127.0.0.1", "0.0.0.0"]:
        # 로컬 환경: http만 사용
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

@app.get("/openapi/cs2-swagger2.yaml", include_in_schema=False)
def get_cs2_yaml(request: Request):
    # Try multiple possible paths
    possible_paths = [
        BASE_DIR / "openapi" / "cs2-swagger2.yaml",
        pathlib.Path("/app/openapi/cs2-swagger2.yaml"),
        pathlib.Path("openapi/cs2-swagger2.yaml"),
    ]
    
    yaml_path = None
    for path in possible_paths:
        if path.exists():
            yaml_path = path
            break
    
    if not yaml_path:
        logger.error(f"YAML file not found. Tried: {possible_paths}")
        raise HTTPException(404, f"File not found. Tried: {possible_paths}")
    
    logger.info(f"Serving YAML file: {yaml_path}")
    from fastapi.responses import Response
    import re
    
    content = yaml_path.read_text(encoding="utf-8")
    
    # 동적으로 host 변경
    current_host = request.url.hostname
    current_port = request.url.port
    current_scheme = request.url.scheme
    
    # Cloud Run 환경 감지 (K_SERVICE 환경 변수 또는 .run.app 도메인)
    import os
    is_cloud_run = os.getenv("K_SERVICE") is not None or current_host.endswith(".run.app")
    
    # 0.0.0.0을 localhost로 변경
    if current_host == "0.0.0.0":
        current_host = "localhost"
    
    # Cloud Run이면 포트 제거, 로컬이면 포트 포함
    if is_cloud_run:
        # Cloud Run: 포트 없이 host만 사용, https 사용 (포트는 항상 무시)
        # host에서 포트가 포함되어 있으면 제거
        if ":" in current_host:
            dynamic_host = current_host.split(":")[0]
        else:
            dynamic_host = current_host
        dynamic_scheme = "https"
    else:
        # 로컬 환경: 포트 포함
        if current_port:
            dynamic_host = f"{current_host}:{current_port}"
        else:
            if current_scheme == "https":
                dynamic_host = current_host
            else:
                dynamic_host = f"{current_host}:8080"
        dynamic_scheme = current_scheme
    
    # host 라인을 현재 요청의 host로 교체
    content = re.sub(
        r'^host:\s*.*$',
        f'host: {dynamic_host}',
        content,
        flags=re.MULTILINE
    )
    
    # schemes 변경
    if is_cloud_run:
        # Cloud Run: https만 사용
        content = re.sub(
            r'^schemes:\s*\n(\s*-\s*(?:https|http)\s*\n?)+',
            'schemes:\n  - https\n',
            content,
            flags=re.MULTILINE
        )
    elif current_host in ["localhost", "127.0.0.1", "0.0.0.0"]:
        # 로컬 환경: http만 사용
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

@app.get("/cs2-swagger2.yaml", include_in_schema=False)
def get_cs2_yaml_root():
    return get_cs2_yaml()

# ------------------------------------------------------------
# Swagger UI (custom HTML loading dropdown)
# ------------------------------------------------------------
@app.get("/swagger", response_class=HTMLResponse, include_in_schema=False)
def swagger_ui():
    html = (STATIC_DIR / "swagger.html").read_text(encoding="utf-8")
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
