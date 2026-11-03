import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes_websocket import router as websocket_router

from backend.app.api.routes_host import router as host_router
from backend.app.api.routes_player import router as player_router

app = FastAPI()

# Comma-separated frontend origins, set on the host (e.g. "https://play.example.com").
# Falls back to the local Vite dev server when unset.
allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(host_router)
app.include_router(player_router)
app.include_router(websocket_router)