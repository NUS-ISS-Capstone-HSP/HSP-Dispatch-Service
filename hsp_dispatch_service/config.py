from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "hsp-dispatch-service"
    env: str = "dev"
    log_level: str = "INFO"
    log_dir: str = "/root/hsp/logs"

    grpc_host: str = "127.0.0.1"
    grpc_port: int = 50051

    http_host: str = "127.0.0.1"
    http_port: int = 8080

    use_mock_repository: bool = False
    mysql_dsn: str = "mysql+aiomysql://root:root@mysql:3306/dispatch_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HSP_DISPATCH_SERVICE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
