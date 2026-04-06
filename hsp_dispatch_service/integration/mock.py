from dataclasses import dataclass, field
from datetime import datetime

from hsp_dispatch_service.domain.errors import ConflictError, ExternalServiceError, NotFoundError
from hsp_dispatch_service.domain.models import AvailableWorker
from hsp_dispatch_service.integration.interfaces import OrderClient, WorkerScheduleClient


@dataclass(slots=True)
class _WorkerState:
    worker_id: str
    name: str
    skills: list[str]
    region: str
    status: str = "AVAILABLE"


class MockWorkerScheduleClient(WorkerScheduleClient):
    def __init__(self) -> None:
        self._workers: dict[str, _WorkerState] = {
            "worker-001": _WorkerState(
                worker_id="worker-001",
                name="Zhang San",
                skills=["cleaning", "moving"],
                region="nantong",
            ),
            "worker-002": _WorkerState(
                worker_id="worker-002",
                name="Li Si",
                skills=["cleaning", "repair"],
                region="nantong",
            ),
            "worker-003": _WorkerState(
                worker_id="worker-003",
                name="Wang Wu",
                skills=["moving"],
                region="haimen",
            ),
        }
        self._reserved_orders: dict[str, str] = {}
        self._fail_next: set[str] = set()

    def fail_next(self, method_name: str) -> None:
        self._fail_next.add(method_name)

    async def list_available_workers(
        self,
        service_type: str | None,
        region: str | None,
        at_time: datetime | None,
        limit: int,
    ) -> list[AvailableWorker]:
        del at_time
        self._consume_fail("list_available_workers")

        rows = [worker for worker in self._workers.values() if worker.status == "AVAILABLE"]
        if service_type:
            normalized = service_type.strip().lower()
            rows = [row for row in rows if normalized in {skill.lower() for skill in row.skills}]
        if region:
            normalized = region.strip().lower()
            rows = [row for row in rows if row.region.lower() == normalized]

        rows = rows[: max(limit, 0)]
        return [
            AvailableWorker(
                worker_id=row.worker_id,
                name=row.name,
                skills=list(row.skills),
                status=row.status,
            )
            for row in rows
        ]

    async def reserve_worker(self, worker_id: str, order_id: str) -> None:
        self._consume_fail("reserve_worker")
        worker = self._workers.get(worker_id)
        if worker is None:
            raise NotFoundError(f"worker '{worker_id}' not found")
        if worker.status != "AVAILABLE":
            raise ConflictError(f"worker '{worker_id}' is not available")

        worker.status = "BUSY"
        self._reserved_orders[order_id] = worker_id

    async def release_worker(self, worker_id: str, order_id: str) -> None:
        self._consume_fail("release_worker")
        worker = self._workers.get(worker_id)
        if worker is None:
            raise NotFoundError(f"worker '{worker_id}' not found")

        reserved_worker = self._reserved_orders.get(order_id)
        if reserved_worker is not None and reserved_worker != worker_id:
            raise ConflictError(
                f"order '{order_id}' is reserved by worker '{reserved_worker}', not '{worker_id}'",
            )

        worker.status = "AVAILABLE"
        self._reserved_orders.pop(order_id, None)

    def _consume_fail(self, method_name: str) -> None:
        if method_name in self._fail_next:
            self._fail_next.remove(method_name)
            raise ExternalServiceError(f"mock worker-schedule failure at {method_name}")


@dataclass(slots=True)
class _OrderState:
    order_id: str
    status: str = "NEW"
    worker_id: str | None = None
    history: list[str] = field(default_factory=list)


class MockOrderClient(OrderClient):
    def __init__(self) -> None:
        self._orders: dict[str, _OrderState] = {}
        self._fail_next: set[str] = set()

    def fail_next(self, method_name: str) -> None:
        self._fail_next.add(method_name)

    async def mark_order_dispatched(self, order_id: str, worker_id: str) -> None:
        self._consume_fail("mark_order_dispatched")
        order = self._orders.setdefault(order_id, _OrderState(order_id=order_id))
        order.status = "DISPATCH_PENDING_CONFIRM"
        order.worker_id = worker_id
        order.history.append(order.status)

    async def mark_order_pending_assignment(self, order_id: str) -> None:
        self._consume_fail("mark_order_pending_assignment")
        order = self._orders.setdefault(order_id, _OrderState(order_id=order_id))
        order.status = "PENDING_REASSIGNMENT"
        order.worker_id = None
        order.history.append(order.status)

    async def mark_order_confirmed(self, order_id: str, worker_id: str) -> None:
        self._consume_fail("mark_order_confirmed")
        order = self._orders.setdefault(order_id, _OrderState(order_id=order_id))
        order.status = "WORKER_CONFIRMED"
        order.worker_id = worker_id
        order.history.append(order.status)

    def _consume_fail(self, method_name: str) -> None:
        if method_name in self._fail_next:
            self._fail_next.remove(method_name)
            raise ExternalServiceError(f"mock order-service failure at {method_name}")
