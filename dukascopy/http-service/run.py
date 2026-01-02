#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        run.py
 Author:      JP Ueberbach
 Created:     2026-01-02
 Description: FastAPI application entrypoint for OHLCV API.

              This module defines the FastAPI application that exposes
              OHLCV (Open, High, Low, Close, Volume) time-series data
              endpoints. It includes:

              - Application setup and lifecycle management
              - Router inclusion for versioned OHLCV API endpoints
              - Health-check and root endpoints
              - Uvicorn-based server startup configuration

              Responsibilities:

              - Manage application lifespan with resource optimization hooks
              - Register routes for OHLCV data access
              - Provide health-check endpoints for monitoring
              - Configure Uvicorn server with uvloop and httptools

 Requirements:
     - Python 3.8+
     - FastAPI
     - Uvicorn with uvloop and httptools

 License:
     MIT License
===============================================================================
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import List
from pathlib import Path
import uvicorn

# Import versioned OHLCV routes
from routes import router as ohlcv_router
from version import API_VERSION

# Lifespan context manager for startup/shutdown hooks
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle events."""
    print("Server starting: Optimizing resources...")
    yield  # Application is running
    print("Server shutting down...")

# Initialize FastAPI application
app = FastAPI(
    title="OHLC API - FastAPI",
    version=API_VERSION,
    lifespan=lifespan
)

# Include the OHLCV API router
app.include_router(ohlcv_router)

# Health-check endpoint for monitoring or load balancers
@app.get("/healthz", status_code=200)
async def health_check():
    """Return a simple online status for health-check purposes."""
    return {"status": "online"}

# This we need to do outside of the main routine because of the StaticFiles below
from config.app_config import load_app_config
config_file = 'config.user.yaml' if Path('config.user.yaml').exists() else 'config.yaml'
app_config = load_app_config(config_file)
config = app_config.http

# Resolve the absolute path for docs directory
docs_path = Path(config.docs).resolve()
if not docs_path.exists():
    print(f"ERROR: Docs directory not found at {docs_path}") 

# Root endpoint for html files
app.mount("/", StaticFiles(directory=docs_path, html=True), name="docs")

# Entrypoint for running the FastAPI app with Uvicorn
if __name__ == "__main__":
    ip, port = config.listen.split(':', 1)

    uvicorn.run(
        "run:app",          # Module and app instance
        host="127.0.0.1",   # Sorry, only localhost
        port=int(port),     # Default port
        loop="uvloop",      # High-performance event loop
        http="httptools",   # HTTP protocol parser
        reload=True         # Auto-reload on code changes
    )
