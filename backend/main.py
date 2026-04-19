from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api import router as api_router
from data.generate_mock_data import ensure_mock_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_mock_data()
    yield


app = FastAPI(title="Delotiee Agent API", version="0.1.0", lifespan=lifespan)

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
