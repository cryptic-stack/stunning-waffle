from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_redis_client
from app.schemas import HealthResponse, ReadinessCheckResponse, ReadinessResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service="api")


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    tags=["health"],
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readyz(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
) -> ReadinessResponse:
    checks: dict[str, ReadinessCheckResponse] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = ReadinessCheckResponse(ok=True)
    except Exception as exc:  # pragma: no cover - defensive runtime path
        checks["database"] = ReadinessCheckResponse(ok=False, detail=str(exc))

    try:
        redis_client.ping()
        checks["redis"] = ReadinessCheckResponse(ok=True)
    except Exception as exc:  # pragma: no cover - defensive runtime path
        checks["redis"] = ReadinessCheckResponse(ok=False, detail=str(exc))

    startup_check = getattr(request.app.state, "worker_image_validation", None)
    if isinstance(startup_check, dict):
        checks["worker_images"] = ReadinessCheckResponse(
            ok=bool(startup_check.get("ok")),
            detail=startup_check.get("detail"),
        )
    else:
        checks["worker_images"] = ReadinessCheckResponse(
            ok=True,
            detail="Startup validation unavailable",
        )

    all_ok = all(check.ok for check in checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if all_ok else "not_ready",
        service="api",
        checks=checks,
    )
