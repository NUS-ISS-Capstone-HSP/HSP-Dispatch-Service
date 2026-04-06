from fastapi.testclient import TestClient

from hsp_dispatch_service.integration.mock import MockOrderClient, MockWorkerScheduleClient
from hsp_dispatch_service.repository.in_memory import InMemoryDispatchRepository
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.http.app import create_http_app


def build_client() -> TestClient:
    service = DispatchService(
        repository=InMemoryDispatchRepository(),
        order_client=MockOrderClient(),
        worker_schedule_client=MockWorkerScheduleClient(),
    )
    app = create_http_app(service)
    return TestClient(app)


def test_healthz_success() -> None:
    client = build_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_available_workers_success() -> None:
    client = build_client()

    response = client.get("/api/dispatch/v1/workers/available", params={"service_type": "cleaning"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["workers"]) >= 1
    assert payload["workers"][0]["status"] == "AVAILABLE"


def test_manual_assign_and_pending_success() -> None:
    client = build_client()

    assign = client.post(
        "/api/dispatch/v1/dispatches/manual",
        json={"order_id": "order-http-1", "worker_id": "worker-001", "operator_id": "csr-001"},
    )
    pending = client.get("/api/dispatch/v1/workers/worker-001/pending-dispatches")

    assert assign.status_code == 201
    assert assign.json()["status"] == "PENDING"
    assert pending.status_code == 200
    assert len(pending.json()["dispatches"]) == 1


def test_confirm_reject_and_reassign_success() -> None:
    client = build_client()

    assign = client.post(
        "/api/dispatch/v1/dispatches/manual",
        json={"order_id": "order-http-2", "worker_id": "worker-001", "operator_id": "csr-001"},
    )
    dispatch_id = assign.json()["dispatch_id"]

    reject = client.post(
        f"/api/dispatch/v1/workers/worker-001/dispatches/{dispatch_id}/response",
        json={"response": "REJECT", "reject_reason": "busy"},
    )
    reassign = client.post(
        "/api/dispatch/v1/dispatches/manual",
        json={"order_id": "order-http-2", "worker_id": "worker-001", "operator_id": "csr-002"},
    )

    assert reject.status_code == 200
    assert reject.json()["status"] == "REJECTED"
    assert reassign.status_code == 201
    assert reassign.json()["attempt_no"] == 2


def test_manual_assign_conflict() -> None:
    client = build_client()

    first = client.post(
        "/api/dispatch/v1/dispatches/manual",
        json={"order_id": "order-http-3", "worker_id": "worker-001", "operator_id": "csr-001"},
    )
    second = client.post(
        "/api/dispatch/v1/dispatches/manual",
        json={"order_id": "order-http-3", "worker_id": "worker-002", "operator_id": "csr-002"},
    )

    assert first.status_code == 201
    assert second.status_code == 409
