from datetime import datetime
from typing import Protocol

from hsp_dispatch_service.domain.models import AvailableWorker


class WorkerScheduleClient(Protocol):
    async def list_available_workers(
        self,
        service_type: str | None,
        region: str | None,
        at_time: datetime | None,
        limit: int,
    ) -> list[AvailableWorker]:
        ...

    async def reserve_worker(self, worker_id: str, order_id: str) -> None:
        ...

    async def release_worker(self, worker_id: str, order_id: str) -> None:
        ...


class OrderClient(Protocol):
    async def mark_order_dispatched(self, order_id: str, worker_id: str) -> None:
        ...

    async def mark_order_pending_assignment(self, order_id: str) -> None:
        ...

    async def mark_order_confirmed(self, order_id: str, worker_id: str) -> None:
        ...
