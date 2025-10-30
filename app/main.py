from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging

# Import all modules
from api import auth, trucks, orders, ws, uploads
from core.config import settings
from db.database import init_db_and_session 
from db.redis import init_redis_pool, close_redis_pool 

import os # remove in prod

log = logging.getLogger(__name__)

STORAGE_DIR = "uploaded_files"

# 1. Define the Lifespan Context Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the application (DB and Redis).
    """
    # --- STARTUP ---
    log.info("Starting up database and redis connections...")
    
    await init_db_and_session(create_tables=True) 
    await init_redis_pool()
    
    log.info("Startup complete.")
    yield
    
    # --- SHUTDOWN ---
    log.info("Shutting down connections...")
    await close_redis_pool()
    log.info("Shutdown complete.")


def create_application() -> FastAPI:
    """
    Initializes and configures the FastAPI application.
    """
    application = FastAPI(
        title="Food Truck Finder API",
        description="A production-ready food truck tracking and ordering service.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan # Use the lifespan manager
    )

    
    # CRITICAL: Configure static file serving for uploaded images
    # Files saved to the local directory 'uploaded_files' are now accessible via the URL '/static/'
    application.mount("/static", StaticFiles(directory=STORAGE_DIR), name="static")

    # 2. Include API Routers
    application.include_router(auth.router, prefix="/api/v1") 
    application.include_router(trucks.router, prefix="/api/v1") 
    application.include_router(orders.router, prefix="/api/v1") 
    application.include_router(ws.router, prefix="/api/v1") 
    application.include_router(uploads.router, prefix="/api/v1")
    
    @application.get("/health")
    def health_check():
        """Simple health check endpoint for load balancers."""
        return {"status": "ok", "version": application.version}

    return application

app = create_application()

# Note: remove in prod
ENV = os.getenv("ENVIRONMENT","DEV")

if ENV == "DEV":
    
    allowed_origins = [
    "*"  # Allows any port on localhost
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


if __name__ == "__main__":
    uvicorn.run(app,port=8000)
