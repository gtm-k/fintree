"""FinTree API — FastAPI server for the P&L hierarchy tree."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from fintree_api.routers import nodes, search, tree, industry, non_gaap

app = FastAPI(
    title="FinTree API",
    description="Canonical GAAP P&L hierarchy tree — interactive ontology for humans and AI agents",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(nodes.router)
app.include_router(search.router)
app.include_router(tree.router)
app.include_router(industry.router)
app.include_router(non_gaap.router)

# Serve frontend static files
_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "static"


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(_WEB_DIR / "index.html")


if _WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")
