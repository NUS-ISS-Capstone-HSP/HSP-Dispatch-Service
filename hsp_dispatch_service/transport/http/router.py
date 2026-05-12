import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Path, Query

from hsp_dispatch_service.domain.models import WorkerResponse
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.http.mapper import (
    to_available_workers_response,
    to_dispatch_record_list_response,
    to_dispatch_record_response,
)
from hsp_dispatch_service.transport.http.schemas import (
    DispatchRecordListResponse,
    DispatchRecordResponse,
    ListAvailableWorkersResponse,
    ManualAssignRequest,
    WorkerResponseRequest,
)

logger = logging.getLogger("uvicorn.error")


def build_router(dispatch_service: DispatchService) -> APIRouter:
    router = APIRouter(prefix="/api/dispatch/v1", tags=["dispatch"])

    @router.get(
        "/workers/available",
        response_model=ListAvailableWorkersResponse,
        summary="List available workers",
        responses={
            400: {"description": "Business validation failed."},
            503: {"description": "Dependent service unavailable."},
        },
    )
    async def list_available_workers(
        service_type: Annotated[str | None, Query()] = None,
        region: Annotated[str | None, Query()] = None,
        at_time: Annotated[datetime | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> ListAvailableWorkersResponse:
        workers = await dispatch_service.list_available_workers(
            service_type=service_type,
            region=region,
            at_time=at_time,
            limit=limit,
        )
        return to_available_workers_response(workers)

    @router.post(
        "/dispatches/manual",
        response_model=DispatchRecordResponse,
        status_code=201,
        summary="Manually assign order",
        responses={
            400: {"description": "Business validation failed."},
            404: {"description": "Resource not found."},
            409: {"description": "Order already has pending dispatch or worker unavailable."},
            503: {"description": "Dependent service unavailable."},
        },
    )
    async def manual_assign(
        payload: ManualAssignRequest,
        x_user_id: Annotated[str | None, Header(alias="x-user-id")] = None,
    ) -> DispatchRecordResponse:
        operator_id = _require_user_id_header(x_user_id)
        record = await dispatch_service.manual_assign_order(
            order_id=payload.order_id,
            worker_id=payload.worker_id,
            operator_id=operator_id,
        )
        logger.info(
            "HTTP_MANUAL_ASSIGN_CREATED order_id=%s worker_id=%s operator_id=%s dispatch_id=%s",
            record.order_id,
            record.worker_id,
            operator_id,
            record.id,
        )
        return to_dispatch_record_response(record)

    @router.get(
        "/workers/pending-dispatches",
        response_model=DispatchRecordListResponse,
        summary="List worker pending dispatches",
        responses={
            400: {"description": "Business validation failed."},
        },
    )
    async def list_pending_dispatches(
        x_user_id: Annotated[str | None, Header(alias="x-user-id")] = None,
    ) -> DispatchRecordListResponse:
        worker_id = _require_user_id_header(x_user_id)
        records = await dispatch_service.list_worker_pending_dispatches(worker_id)
        return to_dispatch_record_list_response(records)

    @router.post(
        "/dispatches/{dispatch_id}/response",
        response_model=DispatchRecordResponse,
        summary="Confirm worker response",
        responses={
            400: {"description": "Business validation failed."},
            404: {"description": "Dispatch not found."},
            409: {"description": "Dispatch already responded."},
            503: {"description": "Dependent service unavailable."},
        },
    )
    async def confirm_worker_response(
        payload: WorkerResponseRequest,
        dispatch_id: str = Path(..., description="Dispatch id."),
        x_user_id: Annotated[str | None, Header(alias="x-user-id")] = None,
    ) -> DispatchRecordResponse:
        worker_id = _require_user_id_header(x_user_id)
        record = await dispatch_service.confirm_worker_response(
            dispatch_id=dispatch_id,
            worker_id=worker_id,
            response=WorkerResponse(payload.response),
            reject_reason=payload.reject_reason,
        )
        logger.info(
            "HTTP_WORKER_RESPONSE_CONFIRMED dispatch_id=%s worker_id=%s response=%s",
            record.id,
            worker_id,
            record.status.value,
        )
        return to_dispatch_record_response(record)

    @router.get(
        "/dispatches",
        response_model=DispatchRecordListResponse,
        summary="List all dispatch records",
        responses={
            400: {"description": "Business validation failed."},
        },
    )
    async def list_dispatches(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> DispatchRecordListResponse:
        records = await dispatch_service.list_dispatches(limit=limit, offset=offset)
        return to_dispatch_record_list_response(records)

    @router.get(
        "/orders/{order_id}/dispatch-history",
        response_model=DispatchRecordListResponse,
        summary="Get order dispatch history",
        responses={
            400: {"description": "Business validation failed."},
        },
    )
    async def get_order_history(
        order_id: str = Path(..., description="Order id."),
    ) -> DispatchRecordListResponse:
        records = await dispatch_service.get_order_dispatch_history(order_id)
        return to_dispatch_record_list_response(records)

    return router


def _require_user_id_header(x_user_id: str | None) -> str:
    normalized = (x_user_id or "").strip()
    if not normalized:
        raise HTTPException(status_code=401, detail="x-user-id header is required")
    return normalized
