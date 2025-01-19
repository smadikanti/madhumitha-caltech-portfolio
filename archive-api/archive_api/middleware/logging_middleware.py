"""Structured JSON request logging with correlation IDs."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("archive_api.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a unique request_id and emit a structured JSON access log line."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
