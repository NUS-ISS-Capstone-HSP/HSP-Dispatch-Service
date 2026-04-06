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


def create_http_app(dispatch_service: DispatchService) -> FastAPI:
    app = FastAPI(title="HSP Dispatch Service")
    app.include_router(build_router(dispatch_service))

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
