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
from contextlib import asynccontextmanager
from typing import List
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

# Root endpoint for basic API info
@app.get("/", status_code=200)
async def root():
    """Return a basic greeting or info message at the API root."""
    return {"status": "online", "message": "Hi there!"}

# Entrypoint for running the FastAPI app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "run:app",          # Module and app instance
        host="0.0.0.0",     # Listen on all interfaces
        port=8000,          # Default port
        loop="uvloop",      # High-performance event loop
        http="httptools",   # HTTP protocol parser
        reload=True         # Auto-reload on code changes
    )
