from dataclasses import dataclass

import grpc
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from hsp_dispatch_service.config import Settings, get_settings
from hsp_dispatch_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_dispatch_service.integration.interfaces import OrderClient, WorkerScheduleClient
from hsp_dispatch_service.integration.mock import MockOrderClient, MockWorkerScheduleClient
from hsp_dispatch_service.repository.in_memory import InMemoryDispatchRepository
from hsp_dispatch_service.repository.interfaces import DispatchRepository
from hsp_dispatch_service.repository.mysql import SQLAlchemyDispatchRepository
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.grpc.server import build_grpc_server
from hsp_dispatch_service.transport.http.app import create_http_app


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine | None
    session_factory: async_sessionmaker[AsyncSession] | None
    dispatch_repository: DispatchRepository
    order_client: OrderClient
    worker_schedule_client: WorkerScheduleClient
    dispatch_service: DispatchService
    http_app: FastAPI
    grpc_server: grpc.aio.Server


async def build_container() -> AppContainer:
    settings = get_settings()
    repository: DispatchRepository

    if settings.use_mock_repository:
        engine = None
        session_factory = None
        repository = InMemoryDispatchRepository()
    else:
        engine = create_engine(settings.mysql_dsn)
        await init_db(engine)
        session_factory = create_session_factory(engine)
        repository = SQLAlchemyDispatchRepository(session_factory)

    order_client = MockOrderClient()
    worker_schedule_client = MockWorkerScheduleClient()
    dispatch_service = DispatchService(repository, order_client, worker_schedule_client)
    http_app = create_http_app(dispatch_service)
    grpc_server = build_grpc_server(settings, dispatch_service)

    return AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        dispatch_repository=repository,
        order_client=order_client,
        worker_schedule_client=worker_schedule_client,
        dispatch_service=dispatch_service,
        http_app=http_app,
        grpc_server=grpc_server,
    )
