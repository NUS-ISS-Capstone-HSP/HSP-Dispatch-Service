from datetime import UTC, datetime

from hsp_dispatch_service.domain.errors import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from hsp_dispatch_service.domain.models import (
    AvailableWorker,
    DispatchRecord,
    DispatchStatus,
    WorkerResponse,
)
from hsp_dispatch_service.integration.interfaces import OrderClient, WorkerScheduleClient
from hsp_dispatch_service.repository.interfaces import DispatchRepository


class DispatchService:
    def __init__(
        self,
        repository: DispatchRepository,
        order_client: OrderClient,
        worker_schedule_client: WorkerScheduleClient,
    ) -> None:
        self._repository = repository
        self._order_client = order_client
        self._worker_schedule_client = worker_schedule_client

    async def list_available_workers(
        self,
        service_type: str | None,
        region: str | None,
        at_time: datetime | None,
        limit: int,
    ) -> list[AvailableWorker]:
        normalized_limit = limit if limit > 0 else 20
        if normalized_limit > 100:
            raise ValidationError("limit must not exceed 100")

        normalized_service_type = _normalize_optional(service_type)
        normalized_region = _normalize_optional(region)
        return await self._worker_schedule_client.list_available_workers(
            normalized_service_type,
            normalized_region,
            at_time,
            normalized_limit,
        )

    async def manual_assign_order(
        self,
        order_id: str,
        worker_id: str,
        operator_id: str,
    ) -> DispatchRecord:
        normalized_order_id = _normalize_required(order_id, "order_id")
        normalized_worker_id = _normalize_required(worker_id, "worker_id")
        normalized_operator_id = _normalize_required(operator_id, "operator_id")

        if await self._repository.has_pending_dispatch(normalized_order_id):
            raise ConflictError(f"order '{normalized_order_id}' already has a pending dispatch")

        attempt_no = await self._repository.get_latest_attempt_no(normalized_order_id) + 1
        assigned_at = datetime.now(UTC)

        worker_reserved = False
        order_marked = False
        try:
            await self._worker_schedule_client.reserve_worker(
                normalized_worker_id,
                normalized_order_id,
            )
            worker_reserved = True
            await self._order_client.mark_order_dispatched(
                normalized_order_id,
                normalized_worker_id,
            )
            order_marked = True
            return await self._repository.create_dispatch(
                order_id=normalized_order_id,
                attempt_no=attempt_no,
                worker_id=normalized_worker_id,
                operator_id=normalized_operator_id,
                assigned_at=assigned_at,
            )
        except (ValidationError, NotFoundError, ConflictError):
            if worker_reserved:
                await self._safe_release_worker(normalized_worker_id, normalized_order_id)
            raise
        except Exception as exc:
            await self._compensate_manual_assign(
                order_id=normalized_order_id,
                worker_id=normalized_worker_id,
                order_marked=order_marked,
                worker_reserved=worker_reserved,
            )
            raise ExternalServiceError("manual dispatch failed and has been compensated") from exc

    async def list_worker_pending_dispatches(self, worker_id: str) -> list[DispatchRecord]:
        normalized_worker_id = _normalize_required(worker_id, "worker_id")
        return await self._repository.list_pending_by_worker(normalized_worker_id)

    async def confirm_worker_response(
        self,
        dispatch_id: str,
        worker_id: str,
        response: WorkerResponse,
        reject_reason: str | None,
    ) -> DispatchRecord:
        normalized_dispatch_id = _normalize_required(dispatch_id, "dispatch_id")
        normalized_worker_id = _normalize_required(worker_id, "worker_id")
        normalized_reject_reason = _normalize_optional(reject_reason)

        record = await self._repository.get_by_id(normalized_dispatch_id)
        if record is None:
            raise NotFoundError(f"dispatch '{normalized_dispatch_id}' not found")
        if record.worker_id != normalized_worker_id:
            raise ValidationError("worker_id does not match assigned worker")
        if record.status != DispatchStatus.PENDING:
            raise ConflictError(f"dispatch '{normalized_dispatch_id}' is already responded")

        if response == WorkerResponse.ACCEPT:
            if normalized_reject_reason is not None:
                raise ValidationError("reject_reason is only allowed when response is REJECT")
            return await self._handle_accept(record)

        if normalized_reject_reason is None:
            raise ValidationError("reject_reason is required when response is REJECT")
        return await self._handle_reject(record, normalized_reject_reason)

    async def get_order_dispatch_history(self, order_id: str) -> list[DispatchRecord]:
        normalized_order_id = _normalize_required(order_id, "order_id")
        return await self._repository.list_by_order(normalized_order_id)

    async def _handle_accept(self, record: DispatchRecord) -> DispatchRecord:
        responded_at = datetime.now(UTC)
        updated = await self._repository.update_worker_response(
            dispatch_id=record.id,
            status=DispatchStatus.ACCEPTED,
            responded_at=responded_at,
            reject_reason=None,
        )
        if updated is None:
            raise NotFoundError(f"dispatch '{record.id}' not found")

        try:
            await self._order_client.mark_order_confirmed(record.order_id, record.worker_id)
            return updated
        except Exception as exc:
            await self._safe_revert_pending(record.id)
            raise ExternalServiceError("failed to confirm order status") from exc

    async def _handle_reject(self, record: DispatchRecord, reject_reason: str) -> DispatchRecord:
        responded_at = datetime.now(UTC)
        updated = await self._repository.update_worker_response(
            dispatch_id=record.id,
            status=DispatchStatus.REJECTED,
            responded_at=responded_at,
            reject_reason=reject_reason,
        )
        if updated is None:
            raise NotFoundError(f"dispatch '{record.id}' not found")

        worker_released = False
        try:
            await self._worker_schedule_client.release_worker(record.worker_id, record.order_id)
            worker_released = True
            await self._order_client.mark_order_pending_assignment(record.order_id)
            return updated
        except Exception as exc:
            if worker_released:
                await self._safe_reserve_worker(record.worker_id, record.order_id)
            await self._safe_revert_pending(record.id)
            raise ExternalServiceError("failed to process reject response") from exc

    async def _compensate_manual_assign(
        self,
        order_id: str,
        worker_id: str,
        order_marked: bool,
        worker_reserved: bool,
    ) -> None:
        if order_marked:
            await self._safe_mark_order_pending(order_id)
        if worker_reserved:
            await self._safe_release_worker(worker_id, order_id)

    async def _safe_release_worker(self, worker_id: str, order_id: str) -> None:
        try:
            await self._worker_schedule_client.release_worker(worker_id, order_id)
        except Exception:
            pass

    async def _safe_reserve_worker(self, worker_id: str, order_id: str) -> None:
        try:
            await self._worker_schedule_client.reserve_worker(worker_id, order_id)
        except Exception:
            pass

    async def _safe_mark_order_pending(self, order_id: str) -> None:
        try:
            await self._order_client.mark_order_pending_assignment(order_id)
        except Exception:
            pass

    async def _safe_revert_pending(self, dispatch_id: str) -> None:
        try:
            await self._repository.revert_to_pending(dispatch_id)
        except Exception:
            pass


def _normalize_required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field_name} must not be empty")
    return normalized


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
