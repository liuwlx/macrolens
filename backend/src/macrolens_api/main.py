from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_client import make_asgi_app

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ModuleNotFoundError:  # Optional for local schema tooling; installed in production image.
    trace = None  # type: ignore[assignment]
    OTLPSpanExporter = None  # type: ignore[assignment,misc]
    FastAPIInstrumentor = None  # type: ignore[assignment,misc]
    Resource = None  # type: ignore[assignment,misc]
    TracerProvider = None  # type: ignore[assignment,misc]
    BatchSpanProcessor = None  # type: ignore[assignment,misc]

from .config import get_settings
from .db import dispose_engine
from .errors import AppError, app_error_handler
from .logging import configure_logging, get_logger
from .middleware import AuditMiddleware, CsrfOriginMiddleware, LocalRateLimitMiddleware, RequestContextMiddleware
from .routers import admin, ai, auth, compare, documents, fomc, health, releases, reports, series, sharing, taxonomies, workspace

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("application_start", environment=settings.environment)
    yield
    await dispose_engine()
    logger.info("application_stop")


app = FastAPI(
    title="MacroLens API",
    version="1.0.2",
    description="宏观数据、发布日历、FOMC、文档检索和 AI 研究平台 API。",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json",
)
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "X-Request-ID"],
)
app.add_middleware(LocalRateLimitMiddleware, requests_per_minute=300)
app.add_middleware(AuditMiddleware)
app.add_middleware(CsrfOriginMiddleware, allowed_origin=settings.web_origin)
app.add_middleware(RequestContextMiddleware)

api_prefix = "/api/v1"
app.include_router(health.router, prefix=api_prefix)
app.include_router(auth.router, prefix=api_prefix)
app.include_router(taxonomies.router, prefix=api_prefix)
app.include_router(series.router, prefix=api_prefix)
app.include_router(compare.router, prefix=api_prefix)
app.include_router(releases.router, prefix=api_prefix)
app.include_router(fomc.router, prefix=api_prefix)
app.include_router(documents.router, prefix=api_prefix)
app.include_router(ai.router, prefix=api_prefix)
app.include_router(workspace.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(sharing.private_router, prefix=api_prefix)
app.include_router(sharing.public_router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
app.mount("/metrics", make_asgi_app())


def configure_telemetry() -> None:
    if FastAPIInstrumentor is None:
        logger.warning("opentelemetry_unavailable")
        return
    if not settings.otel_exporter_otlp_endpoint:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,live,ready,metrics")
        return
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "macrolens-api",
                "service.version": app.version,
                "deployment.environment": settings.environment,
            }
        )
    )
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,live,ready,metrics")


configure_telemetry()
