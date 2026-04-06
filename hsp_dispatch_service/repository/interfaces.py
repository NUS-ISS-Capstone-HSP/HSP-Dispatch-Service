from datetime import datetime
from typing import Protocol

from hsp_dispatch_service.domain.models import DispatchRecord, DispatchStatus


class DispatchRepository(Protocol):
    async def has_pending_dispatch(self, order_id: str) -> bool:
        ...

    async def get_latest_attempt_no(self, order_id: str) -> int:
        ...

    async def create_dispatch(
        self,
        order_id: str,
        attempt_no: int,
        worker_id: str,
        operator_id: str,
        assigned_at: datetime,
    ) -> DispatchRecord:
        ...

    async def get_by_id(self, dispatch_id: str) -> DispatchRecord | None:
        ...

    async def update_worker_response(
        self,
        dispatch_id: str,
        status: DispatchStatus,
        responded_at: datetime,
        reject_reason: str | None,
    ) -> DispatchRecord | None:
        ...

    async def revert_to_pending(self, dispatch_id: str) -> DispatchRecord | None:
        ...

    async def list_pending_by_worker(self, worker_id: str) -> list[DispatchRecord]:
        ...

    async def list_by_order(self, order_id: str) -> list[DispatchRecord]:
        ...
