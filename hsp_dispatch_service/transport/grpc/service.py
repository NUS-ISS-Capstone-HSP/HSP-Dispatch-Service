import logging
from collections.abc import Iterable
from datetime import datetime

import grpc
from google.protobuf.json_format import MessageToDict

from hsp_dispatch_service.domain.errors import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from hsp_dispatch_service.logging import log_event
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.grpc.mapper import (
    to_domain_worker_response,
    to_grpc_dispatch,
    to_grpc_worker,
)
from rpc.dispatch.v1 import dispatch_pb2, dispatch_pb2_grpc

logger = logging.getLogger(__name__)


class DispatchGrpcService(dispatch_pb2_grpc.DispatchServiceServicer):
    def __init__(self, dispatch_service: DispatchService) -> None:
        self._dispatch_service = dispatch_service

    async def ListAvailableWorkers(
        self,
        request: dispatch_pb2.ListAvailableWorkersRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.ListAvailableWorkersResponse:
        _log_grpc_request("ListAvailableWorkers", request, context)
        await _authorize(context, allowed_roles={"customer_service", "admin"})
        try:
            at_time = datetime.fromisoformat(request.at_time) if request.at_time else None
            workers = await self._dispatch_service.list_available_workers(
                service_type=request.service_type or None,
                region=request.region or None,
                at_time=at_time,
                limit=request.limit or 20,
            )
            log_event(
                logger,
                logging.INFO,
                "grpc.list_available_workers.completed",
                rpc="ListAvailableWorkers",
                service_type=request.service_type or None,
                region=request.region or None,
                at_time=request.at_time or None,
                limit=request.limit or 20,
                worker_count=len(workers),
            )
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "at_time must be ISO-8601")
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except ExternalServiceError as exc:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(exc))

        return dispatch_pb2.ListAvailableWorkersResponse(
            workers=[to_grpc_worker(worker) for worker in workers],
        )

    async def ManualAssignOrder(
        self,
        request: dispatch_pb2.ManualAssignOrderRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.ManualAssignOrderResponse:
        _log_grpc_request("ManualAssignOrder", request, context)
        user_id, _ = await _authorize(context, allowed_roles={"customer_service", "admin"})

        try:
            record = await self._dispatch_service.manual_assign_order(
                order_id=request.order_id,
                worker_id=request.worker_id,
                operator_id=user_id,
            )
            log_event(
                logger,
                logging.INFO,
                "grpc.manual_assign.completed",
                rpc="ManualAssignOrder",
                dispatch_id=record.id,
                order_id=record.order_id,
                worker_id=record.worker_id,
                operator_id=user_id,
                status=record.status.value,
            )
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ConflictError as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        except ExternalServiceError as exc:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(exc))

        return dispatch_pb2.ManualAssignOrderResponse(dispatch=to_grpc_dispatch(record))

    async def ListWorkerPendingDispatches(
        self,
        request: dispatch_pb2.ListWorkerPendingDispatchesRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.ListWorkerPendingDispatchesResponse:
        _log_grpc_request("ListWorkerPendingDispatches", request, context)
        user_id, _ = await _authorize(context, allowed_roles={"worker", "admin"})

        try:
            records = await self._dispatch_service.list_worker_pending_dispatches(user_id)
            log_event(
                logger,
                logging.INFO,
                "grpc.list_worker_pending_dispatches.completed",
                rpc="ListWorkerPendingDispatches",
                worker_id=user_id,
                dispatch_count=len(records),
            )
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return dispatch_pb2.ListWorkerPendingDispatchesResponse(
            dispatches=[to_grpc_dispatch(record) for record in records],
        )

    async def ConfirmWorkerResponse(
        self,
        request: dispatch_pb2.ConfirmWorkerResponseRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.ConfirmWorkerResponseResponse:
        _log_grpc_request("ConfirmWorkerResponse", request, context)
        user_id, _ = await _authorize(context, allowed_roles={"worker", "admin"})

        try:
            response = to_domain_worker_response(request.response)
            record = await self._dispatch_service.confirm_worker_response(
                dispatch_id=request.dispatch_id,
                worker_id=user_id,
                response=response,
                reject_reason=request.reject_reason or None,
            )
            log_event(
                logger,
                logging.INFO,
                "grpc.confirm_worker_response.completed",
                rpc="ConfirmWorkerResponse",
                dispatch_id=record.id,
                worker_id=user_id,
                response=response.value,
                status=record.status.value,
            )
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ConflictError as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        except ExternalServiceError as exc:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(exc))

        return dispatch_pb2.ConfirmWorkerResponseResponse(dispatch=to_grpc_dispatch(record))

    async def GetOrderDispatchHistory(
        self,
        request: dispatch_pb2.GetOrderDispatchHistoryRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.GetOrderDispatchHistoryResponse:
        _log_grpc_request("GetOrderDispatchHistory", request, context)
        await _authorize(context, allowed_roles={"customer_service", "admin"})
        try:
            records = await self._dispatch_service.get_order_dispatch_history(request.order_id)
            log_event(
                logger,
                logging.INFO,
                "grpc.get_order_dispatch_history.completed",
                rpc="GetOrderDispatchHistory",
                order_id=request.order_id,
                dispatch_count=len(records),
            )
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return dispatch_pb2.GetOrderDispatchHistoryResponse(
            dispatches=[to_grpc_dispatch(record) for record in records],
        )

    async def ListDispatches(
        self,
        request: dispatch_pb2.ListDispatchesRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.ListDispatchesResponse:
        _log_grpc_request("ListDispatches", request, context)
        await _authorize(context, allowed_roles={"customer_service", "admin"})
        try:
            records = await self._dispatch_service.list_dispatches(
                limit=request.limit or 100,
                offset=request.offset,
            )
            log_event(
                logger,
                logging.INFO,
                "grpc.list_dispatches.completed",
                rpc="ListDispatches",
                limit=request.limit or 100,
                offset=request.offset,
                dispatch_count=len(records),
            )
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return dispatch_pb2.ListDispatchesResponse(
            dispatches=[to_grpc_dispatch(record) for record in records],
        )


async def _authorize(
    context: grpc.aio.ServicerContext,
    allowed_roles: Iterable[str],
) -> tuple[str, str]:
    metadata = _get_metadata_map(context)

    user_id = metadata.get("x-user-id", "").strip()
    role = metadata.get("x-user-role", "").strip().lower()
    if not user_id or not role:
        await context.abort(
            grpc.StatusCode.UNAUTHENTICATED,
            "x-user-id and x-user-role are required in metadata",
        )

    normalized_allowed_roles = {item.strip().lower() for item in allowed_roles}
    if role not in normalized_allowed_roles:
        await context.abort(
            grpc.StatusCode.PERMISSION_DENIED,
            f"role '{role}' is not allowed for this rpc",
        )
    return user_id, role


def _get_metadata_map(context: grpc.aio.ServicerContext) -> dict[str, str]:
    return {key.lower(): value for key, value in context.invocation_metadata()}


def _log_grpc_request(
    rpc_name: str,
    request: object,
    context: grpc.aio.ServicerContext,
) -> None:
    request_payload = MessageToDict(
        request,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )
    metadata = _get_metadata_map(context)
    log_event(
        logger,
        logging.INFO,
        "grpc.request.received",
        rpc=rpc_name,
        metadata=metadata,
        params=request_payload,
    )
