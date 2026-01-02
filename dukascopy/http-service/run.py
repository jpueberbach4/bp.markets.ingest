from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager
from typing import List
import uvicorn

# Needs uvcorn, uvloop, fastapi, httptools

# Import routes
from routes import router as ohlcv_router
from version import API_VERSION

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server starting: Optimizing resources...")
    yield
    print("Server shutting down...")

# Setup FastAPI app
app = FastAPI(
    title="OHLC API - FastAPI",
    version=API_VERSION,
    lifespan=lifespan
)
# Include the imported routes
app.include_router(ohlcv_router)

# Define healtz endpoint
@app.get("/healthz", status_code=200)
async def health_check():
    return {"status": "online"}

# Root (change later)
@app.get("/", status_code=200)
async def health_check():
    return {"status": "online", "message": "Hi there!"}

if __name__ == "__main__":
    # Run the app
    uvicorn.run(
        "run:app", 
        host="0.0.0.0", 
        port=8000, 
        loop="uvloop", 
        http="httptools",
        reload=True
    )