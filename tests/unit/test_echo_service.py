import pytest

from hsp_dispatch_service.domain.errors import ConflictError, ExternalServiceError, ValidationError
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
async def test_manual_assign_does_not_call_reserve_worker() -> None:
    worker_client = MockWorkerScheduleClient()
    worker_client.fail_next("reserve_worker")
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=worker_client,
    )

    created = await service.manual_assign_order("order-1b", "worker-001", "csr-001")

    assert created.order_id == "order-1b"
    assert created.status == DispatchStatus.PENDING


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
async def test_reject_response_does_not_call_release_worker() -> None:
    worker_client = MockWorkerScheduleClient()
    worker_client.fail_next("release_worker")
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=worker_client,
    )

    created = await service.manual_assign_order("order-2b", "worker-001", "csr-001")
    rejected = await service.confirm_worker_response(
        dispatch_id=created.id,
        worker_id="worker-001",
        response=WorkerResponse.REJECT,
        reject_reason="busy",
    )

    assert rejected.status == DispatchStatus.REJECTED


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


@pytest.mark.asyncio
async def test_list_dispatches_success() -> None:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )
    await service.manual_assign_order("order-list-1", "worker-001", "csr-001")

    records = await service.list_dispatches(limit=10, offset=0)

    assert len(records) == 1
    assert records[0].order_id == "order-list-1"


@pytest.mark.asyncio
async def test_list_dispatches_invalid_limit_raises_validation_error() -> None:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )

    with pytest.raises(ValidationError):
        await service.list_dispatches(limit=0, offset=0)
