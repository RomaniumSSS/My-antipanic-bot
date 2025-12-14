"""FastAPI application for Telegram Mini App (TMA)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.database.config import close_db, init_db
from src.interfaces.api.routers import goal, history, microhit, stats, user

app = FastAPI(
    title="Antipanic API",
    description="Backend API for Antipanic Telegram Mini App",
    version="1.0.0",
)

# CORS для Vercel (будет обновлено при деплое)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development
        "https://*.vercel.app",  # Vercel preview/production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(user.router, prefix="/api", tags=["user"])
app.include_router(goal.router, prefix="/api", tags=["goals"])
app.include_router(microhit.router, prefix="/api", tags=["microhit"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(history.router, prefix="/api", tags=["history"])


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
