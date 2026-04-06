from datetime import datetime

import grpc

from hsp_dispatch_service.domain.errors import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.grpc.mapper import (
    to_domain_worker_response,
    to_grpc_dispatch,
    to_grpc_worker,
)
from rpc.dispatch.v1 import dispatch_pb2, dispatch_pb2_grpc


class DispatchGrpcService(dispatch_pb2_grpc.DispatchServiceServicer):
    def __init__(self, dispatch_service: DispatchService) -> None:
        self._dispatch_service = dispatch_service

    async def ListAvailableWorkers(
        self,
        request: dispatch_pb2.ListAvailableWorkersRequest,
        context: grpc.aio.ServicerContext,
    ) -> dispatch_pb2.ListAvailableWorkersResponse:
        try:
            at_time = datetime.fromisoformat(request.at_time) if request.at_time else None
            workers = await self._dispatch_service.list_available_workers(
                service_type=request.service_type or None,
                region=request.region or None,
                at_time=at_time,
                limit=request.limit or 20,
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
        try:
            record = await self._dispatch_service.manual_assign_order(
                order_id=request.order_id,
                worker_id=request.worker_id,
                operator_id=request.operator_id,
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
        try:
            records = await self._dispatch_service.list_worker_pending_dispatches(request.worker_id)
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
        try:
            response = to_domain_worker_response(request.response)
            record = await self._dispatch_service.confirm_worker_response(
                dispatch_id=request.dispatch_id,
                worker_id=request.worker_id,
                response=response,
                reject_reason=request.reject_reason or None,
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
        try:
            records = await self._dispatch_service.get_order_dispatch_history(request.order_id)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return dispatch_pb2.GetOrderDispatchHistoryResponse(
            dispatches=[to_grpc_dispatch(record) for record in records],
        )
