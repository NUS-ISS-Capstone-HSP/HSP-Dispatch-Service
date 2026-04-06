from hsp_dispatch_service.domain.models import AvailableWorker, DispatchRecord, WorkerResponse
from rpc.dispatch.v1 import dispatch_pb2


def to_grpc_worker(worker: AvailableWorker) -> dispatch_pb2.Worker:
    return dispatch_pb2.Worker(
        worker_id=worker.worker_id,
        name=worker.name,
        skills=worker.skills,
        status=worker.status,
    )


def to_grpc_dispatch(record: DispatchRecord) -> dispatch_pb2.DispatchRecord:
    return dispatch_pb2.DispatchRecord(
        dispatch_id=record.id,
        order_id=record.order_id,
        attempt_no=record.attempt_no,
        worker_id=record.worker_id,
        operator_id=record.operator_id,
        status=record.status.value,
        assigned_at=record.assigned_at.isoformat(),
        responded_at=record.responded_at.isoformat() if record.responded_at else "",
        reject_reason=record.reject_reason or "",
    )


def to_domain_worker_response(value: dispatch_pb2.WorkerResponseType) -> WorkerResponse:
    if value == dispatch_pb2.WORKER_RESPONSE_TYPE_ACCEPT:
        return WorkerResponse.ACCEPT
    if value == dispatch_pb2.WORKER_RESPONSE_TYPE_REJECT:
        return WorkerResponse.REJECT
    raise ValueError("response must be ACCEPT or REJECT")
