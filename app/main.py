from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.users import users
from app.composite import router as composite_router
import pathlib

app = FastAPI(
    title="LionSwap Identity & Accounts API",
    version="0.1.0",
    description="LionSwap User API",
)

# --- Routers ---
app.include_router(users.router)
app.include_router(composite_router.router)
# --- OpenAPI (Swagger 2.0 YAML) ---
OPENAPI_PATH = pathlib.Path(__file__).parent.parent / "openapi" / "users-swagger2.yaml"

@app.get("/openapi/users-swagger2.yaml", include_in_schema=False)
def get_openapi_yaml():
    # no-cache so Swagger UI always reflects the latest YAML
    return FileResponse(
        OPENAPI_PATH,
        headers={"Cache-Control": "no-store, max-age=0"}
    )

# --- Lightweight Swagger UI that loads your YAML ---
@app.get("/swagger", response_class=HTMLResponse, include_in_schema=False)
def swagger_ui():
    html = (pathlib.Path(__file__).parent.parent / "static" / "swagger.html").read_text(encoding="utf-8")
    # Optional: bump a version query automatically to avoid browser cache on first load
    # You can also hardcode ?v=7 in swagger.html's JS.
    return HTMLResponse(content=html)

# ---- Async operations polling (used by 202 Accepted flows) ----
# Reuse the in-memory operations dict defined in app.users.users
OPS = getattr(users, "_OPS", None)  # dict: op_id -> {"status": "...", "result": {...}}

@app.get("/operations/{op_id}", include_in_schema=False)
def get_operation_status(op_id: str):
    if OPS is None:
        raise HTTPException(status_code=404, detail="Operations store not available")
    op = OPS.get(op_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    return JSONResponse(op)

# --- Convenience: redirect root to Swagger UI ---
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/swagger")

# --- Static assets (the swagger.html page) ---
app.mount(
    "/static",
    StaticFiles(directory=str(pathlib.Path(__file__).parent.parent / "static")),
    name="static",
)
