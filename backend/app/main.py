"""
UNS Platform Backend — FastAPI Application
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.api.v1 import (
    namespace, 
    tags, 
    data, 
    schema_types as payload_schemas, 
    system, 
    ai,
    production_runs
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup / shutdown."""
    # Startup — record start time for uptime tracking
    app.state.start_time = time.time()
    yield
    # Shutdown — dispose engine connection pool.
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.platform_version,
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
app.include_router(payload_schemas.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(production_runs.router, prefix="/api/v1")


# --- Health Check ---
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": settings.app_name}
