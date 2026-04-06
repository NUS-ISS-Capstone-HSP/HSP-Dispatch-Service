from hsp_dispatch_service.domain.models import AvailableWorker, DispatchRecord
from hsp_dispatch_service.transport.http.schemas import (
    AvailableWorkerResponse,
    DispatchRecordListResponse,
    DispatchRecordResponse,
    ListAvailableWorkersResponse,
)


def to_available_workers_response(workers: list[AvailableWorker]) -> ListAvailableWorkersResponse:
    return ListAvailableWorkersResponse(workers=[to_available_worker(worker) for worker in workers])


def to_available_worker(worker: AvailableWorker) -> AvailableWorkerResponse:
    return AvailableWorkerResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        skills=worker.skills,
        status=worker.status,
    )


def to_dispatch_record_response(record: DispatchRecord) -> DispatchRecordResponse:
    return DispatchRecordResponse(
        dispatch_id=record.id,
        order_id=record.order_id,
        attempt_no=record.attempt_no,
        worker_id=record.worker_id,
        operator_id=record.operator_id,
        status=record.status.value,
        assigned_at=record.assigned_at.isoformat(),
        responded_at=record.responded_at.isoformat() if record.responded_at else None,
        reject_reason=record.reject_reason,
    )


def to_dispatch_record_list_response(records: list[DispatchRecord]) -> DispatchRecordListResponse:
    return DispatchRecordListResponse(
        dispatches=[to_dispatch_record_response(record) for record in records],
    )
