"""FastAPI application for Telegram Mini App (TMA)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import config as settings
from src.database.config import close_db, init_db
from src.interfaces.api.routers import dev, goal, history, microhit, stats, user

app = FastAPI(
    title="Antipanic API",
    description="Backend API for Antipanic Telegram Mini App",
    version="1.0.0",
)

# CORS: allow TMA frontend + development
allowed_origins = [
    "http://localhost:3000",  # Local development
]

# Add production TMA URL if configured
if settings.TMA_URL:
    allowed_origins.append(settings.TMA_URL)

# Development: allow all origins if TMA_URL not set
allow_credentials = True
if not settings.TMA_URL and settings.ENVIRONMENT != "production":
    allowed_origins = ["*"]
    allow_credentials = False  # Cannot use credentials with wildcard

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(user.router, prefix="/api", tags=["user"])
app.include_router(goal.router, prefix="/api", tags=["goals"])
app.include_router(microhit.router, prefix="/api", tags=["microhit"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(history.router, prefix="/api", tags=["history"])

# Development-only router (remove in production)
if settings.ENVIRONMENT != "production":
    app.include_router(dev.router, tags=["development"])


@app.on_event("startup")
async def startup():
    """Initialize database connection on startup."""
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    """Close database connection on shutdown."""
    await close_db()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Antipanic API"}


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {"status": "healthy"}
