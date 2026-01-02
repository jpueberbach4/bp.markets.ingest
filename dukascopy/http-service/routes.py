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
    # parse string for SELECT, AFTER, UNTIL, OUTPUT and MT4 
    # http://host:port/ohlcv/1.0/select/SYMBOL,TF1,TF2:skiplast/select/ \
    # SYMBOL,TF1/after/2025-01-01+00:00:00/output/CSV/MT4 \
    # ?page=1&num=10&order=asc|desc&limit=1000
    # select files to evaluate
    # construct DuckDB SQL query
    # execute DuckDB SQL query
    # construct response
    # return response
    # Note: we don't implement a result-id, if user wants to prevent that
    #       pages shift (eg on order descending) because new candles get created, 
    #       the user can use "until"
    return dict({"test":f"{path_str}"})
