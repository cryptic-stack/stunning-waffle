from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.logger = structlog.get_logger("http")

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.settings.correlation_id_header) or uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response = await call_next(request)
        response.headers[self.settings.correlation_id_header] = request_id
        self.logger.info("request_completed", status_code=response.status_code)
        return response
