from pathlib import Path

import pytest

from hsp_dispatch_service.bootstrap.container import build_container
from hsp_dispatch_service.config import get_settings
from hsp_dispatch_service.repository.in_memory import InMemoryDispatchRepository
from hsp_dispatch_service.repository.mysql import SQLAlchemyDispatchRepository


@pytest.mark.asyncio
async def test_build_container_with_mock_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HSP_DISPATCH_SERVICE_USE_MOCK_REPOSITORY", "true")
    monkeypatch.setenv("HSP_DISPATCH_SERVICE_MYSQL_DSN", "mysql+aiomysql://not-used")
    monkeypatch.setenv("HSP_DISPATCH_SERVICE_GRPC_PORT", "0")
    get_settings.cache_clear()

    container = await build_container()

    assert isinstance(container.dispatch_repository, InMemoryDispatchRepository)
    assert container.engine is None
    assert container.session_factory is None

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_build_container_with_sqlalchemy_repository(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "container.db"
    monkeypatch.setenv("HSP_DISPATCH_SERVICE_USE_MOCK_REPOSITORY", "false")
    monkeypatch.setenv("HSP_DISPATCH_SERVICE_MYSQL_DSN", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("HSP_DISPATCH_SERVICE_GRPC_PORT", "0")
    get_settings.cache_clear()

    container = await build_container()

    assert isinstance(container.dispatch_repository, SQLAlchemyDispatchRepository)
    assert container.engine is not None
    assert container.session_factory is not None

    created = await container.dispatch_service.manual_assign_order(
        order_id="order-container",
        worker_id="worker-001",
        operator_id="csr-001",
    )
    fetched = await container.dispatch_service.get_order_dispatch_history("order-container")

    assert created.order_id == "order-container"
    assert len(fetched) == 1

    if container.engine is not None:
        await container.engine.dispose()
    get_settings.cache_clear()
