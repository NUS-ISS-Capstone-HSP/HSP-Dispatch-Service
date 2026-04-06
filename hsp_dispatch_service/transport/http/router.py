from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query

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
    async def manual_assign(payload: ManualAssignRequest) -> DispatchRecordResponse:
        record = await dispatch_service.manual_assign_order(
            order_id=payload.order_id,
            worker_id=payload.worker_id,
            operator_id=payload.operator_id,
        )
        return to_dispatch_record_response(record)

    @router.get(
        "/workers/{worker_id}/pending-dispatches",
        response_model=DispatchRecordListResponse,
        summary="List worker pending dispatches",
        responses={
            400: {"description": "Business validation failed."},
        },
    )
    async def list_pending_dispatches(
        worker_id: str = Path(..., description="Worker id."),
    ) -> DispatchRecordListResponse:
        records = await dispatch_service.list_worker_pending_dispatches(worker_id)
        return to_dispatch_record_list_response(records)

    @router.post(
        "/workers/{worker_id}/dispatches/{dispatch_id}/response",
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
        worker_id: str = Path(..., description="Worker id."),
        dispatch_id: str = Path(..., description="Dispatch id."),
    ) -> DispatchRecordResponse:
        record = await dispatch_service.confirm_worker_response(
            dispatch_id=dispatch_id,
            worker_id=worker_id,
            response=WorkerResponse(payload.response),
            reject_reason=payload.reject_reason,
        )
        return to_dispatch_record_response(record)

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
