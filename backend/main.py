"""
main.py — FastAPI application entry point for the School Management System.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.database import Base, engine
from backend.rate_limit import limiter
from backend.routers import auth as auth_router, admin as admin_router, attendance as attendance_router, homework as homework_router

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
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")
    yield
    logger.info("Shutting down School Management System...")


app = FastAPI(
    title="School Management System",
    description="Module 1 & 2 — Auth + Admin Management",
    version="1.1.0",
    lifespan=lifespan,
)

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


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "School Management System"}
