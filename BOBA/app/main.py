from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from collections import deque
from typing import Dict, Deque
import time

from .settings import settings
from .db import Base, engine, get_db

from .routers import user as user_router
from .routers import chatbot as chatbot_router
from .routers import mood as mood_router
from .routers import auth as auth_router


# --------------------------------------------------
# App
# --------------------------------------------------
app = FastAPI(title="BOBA Backend", version="0.3.0")


# --------------------------------------------------
# CORS (Vite dev)
# --------------------------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # no cookies/auth headers yet
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# DB (dev convenience)
# --------------------------------------------------
Base.metadata.create_all(bind=engine)


# --------------------------------------------------
# Rate Limiter (chat only)
# --------------------------------------------------
RATE_WINDOW_SEC = 60
RATE_MAX_REQS = 10
_rate_buckets: Dict[str, Deque[float]] = {}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Let CORS preflight pass through
    if request.method == "OPTIONS":
        return await call_next(request)

    # Apply limit ONLY to chat endpoints
    if request.url.path.startswith(("/chat/text", "/chat/voice")):
        key = request.client.host if request.client else "unknown"
        now = time.time()
        q = _rate_buckets.setdefault(key, deque())

        # drop timestamps outside the window
        while q and (now - q[0]) > RATE_WINDOW_SEC:
            q.popleft()

        if len(q) >= RATE_MAX_REQS:
            return JSONResponse(
                {"detail": "Too many requests, please slow down."},
                status_code=429,
            )

        q.append(now)

    return await call_next(request)


# --------------------------------------------------
# Routers
# --------------------------------------------------
app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(chatbot_router.router)
app.include_router(mood_router.router)


# --------------------------------------------------
# Debug
# --------------------------------------------------
@app.get("/debug/model")
def debug_model():
    return {
        "provider": settings.default_model_provider,
        "model": settings.default_model_name,
        "has_openai_key": bool(settings.openai_api_key),
    }


# --------------------------------------------------
# Health
# --------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


# --------------------------------------------------
# Root
# --------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "service": "boba-backend"}
