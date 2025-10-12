from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.users import users
import pathlib

app = FastAPI(
    title="LionSwap Identity & Accounts API",
    version="0.1.0",
    description="Sprint 1 stub — all endpoints return 501 Not Implemented."
)

# Wire routes
app.include_router(users.router)

# Serve the exact Swagger 2.0 YAML you provided
OPENAPI_PATH = pathlib.Path(__file__).parent.parent / "openapi" / "users-swagger2.yaml"

@app.get("/openapi/users-swagger2.yaml", include_in_schema=False)
def get_openapi_yaml():
    return FileResponse(OPENAPI_PATH)

# Lightweight Swagger UI that loads your YAML
@app.get("/swagger", response_class=HTMLResponse, include_in_schema=False)
def swagger_ui():
    html = (pathlib.Path(__file__).parent.parent / "static" / "swagger.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

# Static assets (the swagger.html page)
app.mount("/static", StaticFiles(directory=str(pathlib.Path(__file__).parent.parent / "static")), name="static")
