import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes_websocket import router as websocket_router

from backend.app.api.routes_host import router as host_router
from backend.app.api.routes_player import router as player_router
from backend.app.games.timer import run_round_timers


@asynccontextmanager
async def lifespan(app: FastAPI):
    timer = asyncio.create_task(run_round_timers())
    try:
        yield
    finally:
        timer.cancel()
        with suppress(asyncio.CancelledError):
            await timer


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(host_router)
app.include_router(player_router)
app.include_router(websocket_router)
