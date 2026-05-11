from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DispatchStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class WorkerResponse(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


@dataclass(slots=True)
class AvailableWorker:
    worker_id: str
    name: str
    skills: list[str]
    status: str


@dataclass(slots=True)
class DispatchRecord:
    id: str
    order_id: str
    attempt_no: int
    worker_id: str
    operator_id: str
    status: DispatchStatus
    assigned_at: datetime
    responded_at: datetime | None
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime
