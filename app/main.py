"""FastAPI application entrypoint for Prompt2Diagram."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as diagram_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-Powered Technical Diagram Generator & AST Codebase Analyzer using "
        "Python, FastAPI, OpenAI ChatGPT API, and PlantUML."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagram_router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    """Serve the interactive Prompt2Diagram Studio web interface."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
