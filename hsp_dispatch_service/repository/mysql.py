from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hsp_dispatch_service.domain.models import DispatchRecord, DispatchStatus
from hsp_dispatch_service.infrastructure.orm import DispatchRecordORM
from hsp_dispatch_service.repository.interfaces import DispatchRepository


class SQLAlchemyDispatchRepository(DispatchRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def has_pending_dispatch(self, order_id: str) -> bool:
        async with self._session_factory() as session:
            stmt = select(DispatchRecordORM.id).where(
                DispatchRecordORM.order_id == order_id,
                DispatchRecordORM.status == DispatchStatus.PENDING.value,
            )
            result = await session.execute(stmt.limit(1))
            return result.scalar_one_or_none() is not None

    async def get_latest_attempt_no(self, order_id: str) -> int:
        async with self._session_factory() as session:
            stmt = select(func.max(DispatchRecordORM.attempt_no)).where(
                DispatchRecordORM.order_id == order_id,
            )
            result = await session.execute(stmt)
            value = result.scalar_one_or_none()
        return int(value or 0)

    async def create_dispatch(
        self,
        order_id: str,
        attempt_no: int,
        worker_id: str,
        operator_id: str,
        assigned_at: datetime,
    ) -> DispatchRecord:
        now = datetime.now(UTC)
        row = DispatchRecordORM(
            id=str(uuid4()),
            order_id=order_id,
            attempt_no=attempt_no,
            worker_id=worker_id,
            operator_id=operator_id,
            status=DispatchStatus.PENDING.value,
            assigned_at=assigned_at,
            responded_at=None,
            reject_reason=None,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _to_domain(row)

    async def get_by_id(self, dispatch_id: str) -> DispatchRecord | None:
        async with self._session_factory() as session:
            stmt = select(DispatchRecordORM).where(DispatchRecordORM.id == dispatch_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    async def update_worker_response(
        self,
        dispatch_id: str,
        status: DispatchStatus,
        responded_at: datetime,
        reject_reason: str | None,
    ) -> DispatchRecord | None:
        async with self._session_factory() as session:
            stmt = select(DispatchRecordORM).where(DispatchRecordORM.id == dispatch_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.status = status.value
            row.responded_at = responded_at
            row.reject_reason = reject_reason
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
        return _to_domain(row)

    async def revert_to_pending(self, dispatch_id: str) -> DispatchRecord | None:
        async with self._session_factory() as session:
            stmt = select(DispatchRecordORM).where(DispatchRecordORM.id == dispatch_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.status = DispatchStatus.PENDING.value
            row.responded_at = None
            row.reject_reason = None
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
        return _to_domain(row)

    async def list_pending_by_worker(self, worker_id: str) -> list[DispatchRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(DispatchRecordORM)
                .where(
                    DispatchRecordORM.worker_id == worker_id,
                    DispatchRecordORM.status == DispatchStatus.PENDING.value,
                )
                .order_by(DispatchRecordORM.assigned_at.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_to_domain(row) for row in rows]

    async def list_by_order(self, order_id: str) -> list[DispatchRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(DispatchRecordORM)
                .where(DispatchRecordORM.order_id == order_id)
                .order_by(DispatchRecordORM.attempt_no.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_to_domain(row) for row in rows]


def _to_domain(row: DispatchRecordORM) -> DispatchRecord:
    assigned_at = _ensure_tz(row.assigned_at)
    responded_at = _ensure_tz(row.responded_at) if row.responded_at is not None else None

    return DispatchRecord(
        id=row.id,
        order_id=row.order_id,
        attempt_no=row.attempt_no,
        worker_id=row.worker_id,
        operator_id=row.operator_id,
        status=DispatchStatus(row.status),
        assigned_at=assigned_at,
        responded_at=responded_at,
        reject_reason=row.reject_reason,
        created_at=_ensure_tz(row.created_at),
        updated_at=_ensure_tz(row.updated_at),
    )


def _ensure_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
