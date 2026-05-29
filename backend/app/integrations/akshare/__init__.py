"""AkShare third-party data sources with IPv4 enforcement.

East Money's push2 API returns empty responses over IPv6 on some networks.
We monkey-patch socket.getaddrinfo to ensure all AkShare calls use IPv4.
"""

import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

_orig_getaddrinfo = socket.getaddrinfo


def _v4_getaddrinfo(
    host: str, port: int, family: int = 0, *args: Any, **kwargs: Any
) -> Any:
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)


def force_ipv4() -> None:
    """Apply global IPv4 enforcement. Safe to call multiple times."""
    if socket.getaddrinfo is not _v4_getaddrinfo:
        socket.getaddrinfo = _v4_getaddrinfo  # type: ignore[assignment]
        logger.info("IPv4 enforcement enabled for AkShare data sources")
