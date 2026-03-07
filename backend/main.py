"""
main.py — FastAPI application entry point for the School Management System.
"""

import logging
import time
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.database import Base, engine
from backend.rate_limit import limiter
from backend.routers import auth as auth_router, admin as admin_router, attendance as attendance_router, homework as homework_router
from backend.routers import timetable as timetable_module
from backend.routers import events as events_router
from backend.routers import uploads as uploads_router
from backend.routers import certificates as certificates_router
from backend.routers import announcements as announcements_router
from backend.routers import notifications as notifications_router
from backend.routers import calendar as calendar_router
from backend.routers import analytics as analytics_router

# ── Logging Configuration ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("school_system")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    logger.info("Starting up School Management System...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized.")
    except Exception as exc:
        logger.warning(f"Database initialization warning: {exc}")
    yield
    logger.info("Shutting down School Management System...")


app = FastAPI(
    title="School Management System",
    description="Comprehensive School Management System — Auth, Admin, Attendance, Homework, Timetable, Events, Uploads, Certificates, Announcements, Notifications, Calendar, Analytics",
    version="3.0.0",
    lifespan=lifespan,
)

# ── Static file serving for uploads ──────────────────────────────────────────
_UPLOADS_DIR = Path("uploads")
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_UPLOADS_DIR)), name="uploads")

# ── Middleware ───────────────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    logger.info(
        f"RID: {request.scope.get('root_path')} {request.method} {request.url.path} "
        f"Completed in {formatted_process_time}ms | Status: {response.status_code}"
    )
    return response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# ── Rate Limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded for {request.client.host}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many login attempts. Try again later."},
    )

# ── CORS Configuration ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(attendance_router.router)
app.include_router(homework_router.router)

# Phase 1 — Core Academic Engine
app.include_router(timetable_module.admin_router)      # POST/GET /admin/periods|rooms|timetable
app.include_router(timetable_module.timetable_router)  # GET /timetable/class|teacher|student
app.include_router(events_router.router)               # /events/*

# Phase 2 — File Upload, Certificates, Announcements, Notifications
app.include_router(uploads_router.router)              # POST /upload, POST /students/{id}/photo
app.include_router(certificates_router.router)         # POST/GET /certificates/*
app.include_router(announcements_router.router)        # POST/GET /announcements*
app.include_router(notifications_router.router)        # GET/PUT/DELETE /notifications/*

# Phase 3 — Academic Calendar + Analytics Engine
app.include_router(calendar_router.router)             # CRUD /calendar/*
app.include_router(analytics_router.router)            # GET /analytics/*


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "School Management System"}
