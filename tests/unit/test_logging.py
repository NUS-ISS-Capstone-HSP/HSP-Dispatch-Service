import json
import logging
from pathlib import Path

from hsp_dispatch_service.logging import (
    DEFAULT_LOG_DIR,
    LOG_FILE_NAME,
    JsonLogFormatter,
    build_json_log_config,
    log_event,
)


def test_json_log_formatter_outputs_json_and_redacts_sensitive_fields() -> None:
    formatter = JsonLogFormatter()
    logger = logging.getLogger("hsp_dispatch_service.tests")
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg="unit.test",
        args=(),
        exc_info=None,
        extra={
            "event": "unit.test",
            "fields": {
                "order_id": "order-001",
                "metadata": {
                    "authorization": "Bearer secret-token",
                    "x-user-id": "worker-001",
                },
            },
        },
    )

    payload = json.loads(formatter.format(record))

    assert payload["event"] == "unit.test"
    assert payload["fields"]["order_id"] == "order-001"
    assert payload["fields"]["metadata"]["authorization"] == "[REDACTED]"
    assert payload["fields"]["metadata"]["x-user-id"] == "worker-001"


def test_build_json_log_config_uses_required_default_directory() -> None:
    config = build_json_log_config(log_level="INFO")

    assert config["handlers"]["file"]["filename"] == str(DEFAULT_LOG_DIR / LOG_FILE_NAME)


def test_build_json_log_config_allows_test_log_directory(tmp_path: Path) -> None:
    config = build_json_log_config(log_level="debug", log_dir=tmp_path)

    assert config["root"]["level"] == "DEBUG"
    assert config["handlers"]["file"]["filename"] == str(tmp_path / LOG_FILE_NAME)


def test_log_event_uses_json_safe_extra_fields(caplog) -> None:
    logger = logging.getLogger("hsp_dispatch_service.tests")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(logger, logging.INFO, "unit.event", password="secret", status="ok")

    assert caplog.records[0].event == "unit.event"
    assert caplog.records[0].fields == {"password": "[REDACTED]", "status": "ok"}
