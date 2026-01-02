from fastapi import APIRouter, HTTPException, status
from typing import Dict

from version import API_VERSION

# Setup router
router = APIRouter(
    prefix="/ohlcv",
    tags=["ohlcv"]
)

# Setup catch-all /ohlcv/1.0/* route, this is dummy impl atm
@router.get(f"/{API_VERSION}/{{path_str:path}}", response_model=Dict)
async def get_ohlcv(path_str: str):
    return dict({"test":f"{path_str}"})
