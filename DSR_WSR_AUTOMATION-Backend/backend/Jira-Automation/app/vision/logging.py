"""Structured logging for vision API request/response exchanges."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGGER_NAME = "app.vision.api"
_configured = False


def get_vision_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def configure_vision_logging(
    *,
    log_path: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Attach handlers once; safe to call multiple times (first call wins)."""
    global _configured
    logger = get_vision_logger()
    logger.setLevel(level)

    if _configured:
        return logger

    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def log_vision_request(
    *,
    model: str,
    slide_number: int | None,
    image_path: Path,
    user_payload: dict[str, Any],
) -> None:
    logger = get_vision_logger()
    logger.info(
        "VISION REQUEST model=%s slide=%s image=%s payload=%s",
        model,
        slide_number,
        image_path,
        json.dumps(user_payload, ensure_ascii=False),
    )


def log_vision_response(
    *,
    model: str,
    slide_number: int | None,
    content: str,
    attempt: int,
) -> None:
    logger = get_vision_logger()
    logger.info(
        "VISION RESPONSE model=%s slide=%s attempt=%s content=%s",
        model,
        slide_number,
        attempt,
        content,
    )


def log_vision_error(
    *,
    model: str,
    slide_number: int | None,
    attempt: int,
    error: str,
) -> None:
    logger = get_vision_logger()
    logger.error(
        "VISION ERROR model=%s slide=%s attempt=%s error=%s",
        model,
        slide_number,
        attempt,
        error,
    )


def default_log_path(near: Path | None = None) -> Path:
    base = near.parent if near is not None else Path.cwd()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return base / f"vision_api_{stamp}.log"
