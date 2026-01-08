from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, JSONResponse

from api.state import cache
from api.v1_1.version import API_VERSION

# Setup router
router = APIRouter(
    prefix=f"/ohlcv/{API_VERSION}",
    tags=["ohlcv1_0"]
)

@router.get(f"/{{request_uri:path}}")
async def get_ohlcv(
    request_uri: str
):
    return {"status":"failure", "exception": "API 1.1 is not yet supported."}