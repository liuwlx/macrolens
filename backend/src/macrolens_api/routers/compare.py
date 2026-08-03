from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import SessionDep
from ..schemas import CompareRequest, CompareResponse
from ..services.compare import compare_series

router = APIRouter(prefix="/compare", tags=["Compare"])


@router.post("/query", response_model=CompareResponse)
async def compare(payload: CompareRequest, session: SessionDep) -> CompareResponse:
    return await compare_series(session, payload)
