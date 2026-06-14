import json
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hsp_dispatch_service.domain.errors import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from hsp_dispatch_service.logging import log_event, sanitize_log_value
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.http.router import build_router

logger = logging.getLogger(__name__)


def create_http_app(dispatch_service: DispatchService) -> FastAPI:
    app = FastAPI(title="HSP Dispatch Service")
    app.include_router(build_router(dispatch_service))

    @app.middleware("http")
    async def log_http_request(request: Request, call_next):
        started_at = time.perf_counter()
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="replace")
        try:
            body_payload = json.loads(body_text) if body_text else None
        except json.JSONDecodeError:
            body_payload = {"raw_body_length": len(body_bytes), "parse_error": "invalid_json"}

        metadata = dict(request.headers)
        query_params = dict(request.query_params)

        log_event(
            logger,
            logging.INFO,
            "http.request.received",
            method=request.method,
            path=request.url.path,
            query=query_params,
            metadata=sanitize_log_value(metadata),
            body=body_payload,
        )
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "http.request.failed",
                method=request.method,
                path=request.url.path,
                query=query_params,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.INFO,
            "http.request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        log_event(logger, logging.INFO, "http.healthz.checked", path="/healthz")
        return {"status": "ok"}

    @app.exception_handler(ValidationError)
    async def validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ExternalServiceError)
    async def external_service_handler(_: Request, exc: ExternalServiceError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    return app
