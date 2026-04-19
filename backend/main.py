from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
from api import router as api_router
from data.generate_mock_data import ensure_mock_data

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static_frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_mock_data()
    yield


app = FastAPI(title="Sales Multi-Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files (must be after API routes)
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"service": "Sales Multi-Agent Coordination System", "status": "running", "docs": "/docs"}
