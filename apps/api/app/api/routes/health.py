from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service="api")


@router.get("/readyz", response_model=HealthResponse, tags=["health"])
def readyz() -> HealthResponse:
    return HealthResponse(status="ok", service="api")
