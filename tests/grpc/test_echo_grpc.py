import grpc
import pytest
import pytest_asyncio

from hsp_dispatch_service.integration.mock import MockOrderClient, MockWorkerScheduleClient
from hsp_dispatch_service.repository.in_memory import InMemoryDispatchRepository
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.grpc.service import DispatchGrpcService
from rpc.dispatch.v1 import dispatch_pb2, dispatch_pb2_grpc


@pytest_asyncio.fixture
async def grpc_stub() -> dispatch_pb2_grpc.DispatchServiceStub:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )

    server = grpc.aio.server()
    dispatch_pb2_grpc.add_DispatchServiceServicer_to_server(DispatchGrpcService(service), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = dispatch_pb2_grpc.DispatchServiceStub(channel)

    try:
        yield stub
    finally:
        await channel.close()
        await server.stop(0)


@pytest.mark.asyncio
async def test_manual_assign_and_history_success(
    grpc_stub: dispatch_pb2_grpc.DispatchServiceStub,
) -> None:
    created = await grpc_stub.ManualAssignOrder(
        dispatch_pb2.ManualAssignOrderRequest(
            order_id="order-grpc-1",
            worker_id="worker-001",
            operator_id="csr-001",
        )
    )
    history = await grpc_stub.GetOrderDispatchHistory(
        dispatch_pb2.GetOrderDispatchHistoryRequest(order_id="order-grpc-1")
    )

    assert created.dispatch.status == "PENDING"
    assert len(history.dispatches) == 1


@pytest.mark.asyncio
async def test_list_available_workers_success(
    grpc_stub: dispatch_pb2_grpc.DispatchServiceStub,
) -> None:
    response = await grpc_stub.ListAvailableWorkers(
        dispatch_pb2.ListAvailableWorkersRequest(service_type="cleaning", limit=10)
    )

    assert len(response.workers) >= 1


@pytest.mark.asyncio
async def test_confirm_reject_success(grpc_stub: dispatch_pb2_grpc.DispatchServiceStub) -> None:
    created = await grpc_stub.ManualAssignOrder(
        dispatch_pb2.ManualAssignOrderRequest(
            order_id="order-grpc-2",
            worker_id="worker-001",
            operator_id="csr-001",
        )
    )
    confirmed = await grpc_stub.ConfirmWorkerResponse(
        dispatch_pb2.ConfirmWorkerResponseRequest(
            dispatch_id=created.dispatch.dispatch_id,
            worker_id="worker-001",
            response=dispatch_pb2.WORKER_RESPONSE_TYPE_REJECT,
            reject_reason="busy",
        )
    )

    assert confirmed.dispatch.status == "REJECTED"


@pytest.mark.asyncio
async def test_manual_assign_failed_precondition(
    grpc_stub: dispatch_pb2_grpc.DispatchServiceStub,
) -> None:
    await grpc_stub.ManualAssignOrder(
        dispatch_pb2.ManualAssignOrderRequest(
            order_id="order-grpc-3",
            worker_id="worker-001",
            operator_id="csr-001",
        )
    )

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.ManualAssignOrder(
            dispatch_pb2.ManualAssignOrderRequest(
                order_id="order-grpc-3",
                worker_id="worker-002",
                operator_id="csr-002",
            )
        )

    assert exc_info.value.code() == grpc.StatusCode.FAILED_PRECONDITION


@pytest.mark.asyncio
async def test_confirm_not_found(grpc_stub: dispatch_pb2_grpc.DispatchServiceStub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.ConfirmWorkerResponse(
            dispatch_pb2.ConfirmWorkerResponseRequest(
                dispatch_id="missing-dispatch",
                worker_id="worker-001",
                response=dispatch_pb2.WORKER_RESPONSE_TYPE_ACCEPT,
            )
        )

    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND
