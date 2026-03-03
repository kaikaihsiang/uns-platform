"""
UNS Platform Backend — FastAPI Application
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.api.v1 import namespace, tags, data, schema_types


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup / shutdown."""
    # Startup — DB pool is lazy‑initialized by SQLAlchemy, nothing extra needed.
    yield
    # Shutdown — dispose engine connection pool.
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="UNS Namespace Data Platform — Backend API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(namespace.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(schema_types.router, prefix="/api/v1")


# --- Health Check ---
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": settings.app_name}
