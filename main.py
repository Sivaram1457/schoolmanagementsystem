"""
main.py — FastAPI application entry point for the School Management System.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import Base, engine
from routers import auth as auth_router, admin as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="School Management System",
    description="Module 1 & 2 — Auth + Admin Management",
    version="1.1.0",
    lifespan=lifespan,
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(admin_router.router)


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "School Management System"}
