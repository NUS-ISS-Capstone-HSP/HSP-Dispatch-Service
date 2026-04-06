from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from hsp_dispatch_service.domain.models import DispatchRecord, DispatchStatus
from hsp_dispatch_service.repository.interfaces import DispatchRepository


class InMemoryDispatchRepository(DispatchRepository):
    def __init__(self) -> None:
        self._store: dict[str, DispatchRecord] = {}

    async def has_pending_dispatch(self, order_id: str) -> bool:
        return any(
            record.order_id == order_id and record.status == DispatchStatus.PENDING
            for record in self._store.values()
        )

    async def get_latest_attempt_no(self, order_id: str) -> int:
        attempts = [
            record.attempt_no
            for record in self._store.values()
            if record.order_id == order_id
        ]
        if not attempts:
            return 0
        return max(attempts)

    async def create_dispatch(
        self,
        order_id: str,
        attempt_no: int,
        worker_id: str,
        operator_id: str,
        assigned_at: datetime,
    ) -> DispatchRecord:
        now = datetime.now(UTC)
        record = DispatchRecord(
            id=str(uuid4()),
            order_id=order_id,
            attempt_no=attempt_no,
            worker_id=worker_id,
            operator_id=operator_id,
            status=DispatchStatus.PENDING,
            assigned_at=assigned_at,
            responded_at=None,
            reject_reason=None,
            created_at=now,
            updated_at=now,
        )
        self._store[record.id] = record
        return deepcopy(record)

    async def get_by_id(self, dispatch_id: str) -> DispatchRecord | None:
        record = self._store.get(dispatch_id)
        if record is None:
            return None
        return deepcopy(record)

    async def update_worker_response(
        self,
        dispatch_id: str,
        status: DispatchStatus,
        responded_at: datetime,
        reject_reason: str | None,
    ) -> DispatchRecord | None:
        record = self._store.get(dispatch_id)
        if record is None:
            return None

        record.status = status
        record.responded_at = responded_at
        record.reject_reason = reject_reason
        record.updated_at = datetime.now(UTC)
        return deepcopy(record)

    async def revert_to_pending(self, dispatch_id: str) -> DispatchRecord | None:
        record = self._store.get(dispatch_id)
        if record is None:
            return None

        record.status = DispatchStatus.PENDING
        record.responded_at = None
        record.reject_reason = None
        record.updated_at = datetime.now(UTC)
        return deepcopy(record)

    async def list_pending_by_worker(self, worker_id: str) -> list[DispatchRecord]:
        records = [
            deepcopy(record)
            for record in self._store.values()
            if record.worker_id == worker_id and record.status == DispatchStatus.PENDING
        ]
        return sorted(records, key=lambda x: x.assigned_at)

    async def list_by_order(self, order_id: str) -> list[DispatchRecord]:
        records = [
            deepcopy(record)
            for record in self._store.values()
            if record.order_id == order_id
        ]
        return sorted(records, key=lambda x: x.attempt_no)
