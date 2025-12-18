"""
FastAPI application for TMA (Telegram Mini App).

Provides REST API endpoints for the frontend to interact with Antipanic Bot data.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import config
from src.interfaces.api.routers import goal, microhit, stats, step, user

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Antipanic Bot API",
    description="REST API for Telegram Mini App",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS configuration
# AICODE-NOTE: CORS origins include localhost for dev and TMA_URL for production
cors_origins = [
    "http://localhost:3000",  # Local Next.js development
    "http://127.0.0.1:3000",
]

# Add TMA frontend URL if configured
if config.TMA_URL:
    # Handle both with and without trailing slash
    tma_url = config.TMA_URL.rstrip("/")
    cors_origins.append(tma_url)
    logger.info(f"Added TMA URL to CORS origins: {tma_url}")

# AICODE-NOTE: Allow all Vercel preview deployments (for testing branches)
# This enables testing from any Vercel deployment URL
import re

def cors_origin_regex(origin: str) -> bool:
    """Allow localhost and any Vercel deployment."""
    allowed_patterns = [
        r"^https?://localhost:\d+$",
        r"^https?://127\.0\.0\.1:\d+$",
        r"^https://.*\.vercel\.app$",  # All Vercel deployments
    ]
    return any(re.match(pattern, origin) for pattern in allowed_patterns)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https://.*\.vercel\.app$|^https?://localhost:\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(user.router)
app.include_router(goal.router)
app.include_router(stats.router)
app.include_router(step.router)
app.include_router(microhit.router)


@app.get("/api/health")
async def api_health():
    """API health check endpoint."""
    return {"status": "ok", "service": "antipanic-api"}
