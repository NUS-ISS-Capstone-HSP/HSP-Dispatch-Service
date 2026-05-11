import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hsp_dispatch_service.domain.errors import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.http.router import build_router

logger = logging.getLogger("uvicorn.error")


def create_http_app(dispatch_service: DispatchService) -> FastAPI:
    app = FastAPI(title="HSP Dispatch Service")
    app.include_router(build_router(dispatch_service))

    @app.middleware("http")
    async def log_http_request(request: Request, call_next):
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="replace")
        try:
            body_payload = json.loads(body_text) if body_text else None
        except json.JSONDecodeError:
            body_payload = body_text

        metadata = dict(request.headers)
        query_params = dict(request.query_params)

        logger.info(
            "HTTP_REQUEST method=%s path=%s query=%s metadata=%s body=%s",
            request.method,
            request.url.path,
            query_params,
            metadata,
            body_payload,
        )
        return await call_next(request)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
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
