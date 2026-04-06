from datetime import UTC, datetime
from pathlib import Path

import pytest

from hsp_dispatch_service.domain.models import DispatchStatus
from hsp_dispatch_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_dispatch_service.repository.mysql import SQLAlchemyDispatchRepository


@pytest.mark.asyncio
async def test_sqlalchemy_repository_create_and_get(tmp_path: Path) -> None:
    db_file = tmp_path / "dispatch.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyDispatchRepository(create_session_factory(engine))

    created = await repository.create_dispatch(
        order_id="order-1",
        attempt_no=1,
        worker_id="worker-001",
        operator_id="csr-001",
        assigned_at=datetime.now(UTC),
    )
    fetched = await repository.get_by_id(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.status == DispatchStatus.PENDING
    assert fetched.order_id == "order-1"

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlalchemy_repository_update_and_history(tmp_path: Path) -> None:
    db_file = tmp_path / "dispatch-history.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyDispatchRepository(create_session_factory(engine))

    created = await repository.create_dispatch(
        order_id="order-2",
        attempt_no=1,
        worker_id="worker-001",
        operator_id="csr-001",
        assigned_at=datetime.now(UTC),
    )

    updated = await repository.update_worker_response(
        dispatch_id=created.id,
        status=DispatchStatus.REJECTED,
        responded_at=datetime.now(UTC),
        reject_reason="busy",
    )
    history = await repository.list_by_order("order-2")
    pending = await repository.list_pending_by_worker("worker-001")

    assert updated is not None
    assert updated.status == DispatchStatus.REJECTED
    assert updated.reject_reason == "busy"
    assert len(history) == 1
    assert history[0].attempt_no == 1
    assert pending == []

    await engine.dispose()
