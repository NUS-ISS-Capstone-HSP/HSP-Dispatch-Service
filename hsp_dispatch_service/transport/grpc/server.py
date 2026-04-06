import grpc

from hsp_dispatch_service.config import Settings
from hsp_dispatch_service.service.dispatch_service import DispatchService
from hsp_dispatch_service.transport.grpc.service import DispatchGrpcService
from rpc.dispatch.v1 import dispatch_pb2_grpc


def build_grpc_server(settings: Settings, dispatch_service: DispatchService) -> grpc.aio.Server:
    server = grpc.aio.server()
    dispatch_pb2_grpc.add_DispatchServiceServicer_to_server(
        DispatchGrpcService(dispatch_service),
        server,
    )
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    return server
