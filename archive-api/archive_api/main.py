"""FastAPI application factory and top-level route wiring."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text
from a2wsgi import WSGIMiddleware
from starlette.responses import Response

from archive_api.config import settings
from archive_api.dashboard.app import create_dash_app
from archive_api.database import engine
from archive_api.middleware.logging_middleware import RequestLoggingMiddleware
from archive_api.middleware.rate_limiter import RateLimiterMiddleware
from archive_api.routers import exoplanets, export, statistics

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)

logger = logging.getLogger("archive_api")


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        ),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Set up logging on startup; dispose of the engine on shutdown."""
    _configure_logging()
    logger.info("archive-api starting")
    yield
    await engine.dispose()
    logger.info("archive-api shutdown complete")


def create_app() -> FastAPI:
    """Construct and return the fully-wired FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "REST API for querying archived exoplanet datasets, "
            "inspired by the NASA Exoplanet Archive's TAP service."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        RateLimiterMiddleware,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    app.include_router(exoplanets.router)
    app.include_router(statistics.router)
    app.include_router(export.router)

    dash_app = create_dash_app(requests_pathname_prefix="/dashboard/")
    app.mount("/dashboard", WSGIMiddleware(dash_app.server))

    # -- system endpoints --------------------------------------------------

    @app.get("/health", tags=["system"], summary="Health check with DB status")
    async def health() -> dict:
        db_status = "healthy"
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            db_status = "unhealthy"
        return {
            "status": "ok" if db_status == "healthy" else "degraded",
            "database": db_status,
            "version": settings.app_version,
        }

    @app.get("/metrics", tags=["system"], summary="Prometheus metrics")
    async def metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # -- global middleware / handlers --------------------------------------

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        import time

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        REQUEST_COUNT.labels(
            request.method, request.url.path, response.status_code
        ).inc()
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(elapsed)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": str(exc),
                "status_code": 500,
            },
        )

    return app


app = create_app()
