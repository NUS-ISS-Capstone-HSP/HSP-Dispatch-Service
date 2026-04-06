import pytest

from hsp_dispatch_service.domain.errors import ConflictError, ExternalServiceError
from hsp_dispatch_service.domain.models import DispatchStatus, WorkerResponse
from hsp_dispatch_service.integration.mock import MockOrderClient, MockWorkerScheduleClient
from hsp_dispatch_service.repository.in_memory import InMemoryDispatchRepository
from hsp_dispatch_service.service.dispatch_service import DispatchService


@pytest.mark.asyncio
async def test_manual_assign_success() -> None:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )

    created = await service.manual_assign_order("order-1", "worker-001", "csr-001")

    assert created.order_id == "order-1"
    assert created.status == DispatchStatus.PENDING
    assert created.attempt_no == 1


@pytest.mark.asyncio
async def test_manual_assign_pending_conflict() -> None:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )

    await service.manual_assign_order("order-1", "worker-001", "csr-001")

    with pytest.raises(ConflictError):
        await service.manual_assign_order("order-1", "worker-002", "csr-002")


@pytest.mark.asyncio
async def test_reject_then_reassign_attempt_increment() -> None:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )

    first = await service.manual_assign_order("order-2", "worker-001", "csr-001")
    rejected = await service.confirm_worker_response(
        dispatch_id=first.id,
        worker_id="worker-001",
        response=WorkerResponse.REJECT,
        reject_reason="busy",
    )
    second = await service.manual_assign_order("order-2", "worker-001", "csr-002")

    assert rejected.status == DispatchStatus.REJECTED
    assert second.attempt_no == 2


@pytest.mark.asyncio
async def test_accept_response_success() -> None:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )

    created = await service.manual_assign_order("order-3", "worker-002", "csr-001")
    accepted = await service.confirm_worker_response(
        dispatch_id=created.id,
        worker_id="worker-002",
        response=WorkerResponse.ACCEPT,
        reject_reason=None,
    )

    assert accepted.status == DispatchStatus.ACCEPTED
    assert accepted.responded_at is not None


@pytest.mark.asyncio
async def test_manual_assign_external_failure_compensated() -> None:
    order_client = MockOrderClient()
    worker_client = MockWorkerScheduleClient()
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=order_client,
        worker_schedule_client=worker_client,
    )

    order_client.fail_next("mark_order_dispatched")

    with pytest.raises(ExternalServiceError):
        await service.manual_assign_order("order-4", "worker-001", "csr-001")

    workers = await service.list_available_workers(None, None, None, 10)
    worker_ids = {worker.worker_id for worker in workers}
    history = await service.get_order_dispatch_history("order-4")

    assert "worker-001" in worker_ids
    assert history == []
