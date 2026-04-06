from pydantic import BaseModel, ConfigDict, Field


class AvailableWorkerResponse(BaseModel):
    worker_id: str = Field(description="Worker unique id.")
    name: str = Field(description="Worker display name.")
    skills: list[str] = Field(description="Worker skill tags.")
    status: str = Field(description="Worker status from worker-schedule service.")


class ListAvailableWorkersResponse(BaseModel):
    workers: list[AvailableWorkerResponse] = Field(default_factory=list)


class DispatchRecordResponse(BaseModel):
    dispatch_id: str = Field(description="Dispatch record id.")
    order_id: str = Field(description="Order id.")
    attempt_no: int = Field(description="Dispatch attempt sequence per order.")
    worker_id: str = Field(description="Assigned worker id.")
    operator_id: str = Field(description="Operator (customer service staff) id.")
    status: str = Field(description="Dispatch status: PENDING/ACCEPTED/REJECTED.")
    assigned_at: str = Field(description="Assignment time in ISO-8601 format.")
    responded_at: str | None = Field(
        default=None,
        description="Worker response time in ISO-8601 format.",
    )
    reject_reason: str | None = Field(default=None, description="Worker reject reason if rejected.")


class ManualAssignRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_id": "order-1001",
                "worker_id": "worker-001",
                "operator_id": "csr-001",
            }
        },
    )

    order_id: str = Field(min_length=1, max_length=64)
    worker_id: str = Field(min_length=1, max_length=64)
    operator_id: str = Field(min_length=1, max_length=64)


class WorkerResponseRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "response": "REJECT",
                "reject_reason": "busy with previous order",
            }
        },
    )

    response: str = Field(pattern="^(ACCEPT|REJECT)$")
    reject_reason: str | None = Field(default=None, max_length=2048)


class DispatchRecordListResponse(BaseModel):
    dispatches: list[DispatchRecordResponse] = Field(default_factory=list)
