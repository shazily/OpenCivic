"""ClamAV virus scanning via TCP INSTREAM protocol."""

import socket
import struct

import structlog

from app.core.config import settings
from app.core.errors import VirusScanFailed

logger = structlog.get_logger(__name__)


def scan_bytes(data: bytes) -> None:
    """
    Scan file bytes with ClamAV. Raises VirusScanFailed if infected or scan errors.

    Skipped when CLAMAV_ENABLED is false (tests and air-gapped dev without sidecar).
    """
    if not settings.CLAMAV_ENABLED:
        logger.info("clamav_scan_skipped", reason="disabled")
        return

    try:
        with socket.create_connection(
            (settings.CLAMAV_HOST, settings.CLAMAV_PORT),
            timeout=settings.CLAMAV_TIMEOUT_SECONDS,
        ) as sock:
            sock.sendall(b"zINSTREAM\0")
            chunk_size = 2048
            offset = 0
            while offset < len(data):
                chunk = data[offset : offset + chunk_size]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
                offset += chunk_size
            sock.sendall(struct.pack("!I", 0))
            response = sock.recv(4096).decode("utf-8", errors="replace").strip()
    except OSError as exc:
        raise VirusScanFailed(
            message="Virus scanner is unavailable.",
            code="VIRUS_SCANNER_UNAVAILABLE",
        ) from exc

    if not response:
        raise VirusScanFailed(message="Empty response from virus scanner.")

    if "FOUND" in response:
        raise VirusScanFailed(message="File failed virus scan and was rejected.")

    if "OK" not in response and "ok" not in response.lower():
        raise VirusScanFailed(message=f"Unexpected virus scanner response: {response}")

    logger.info("clamav_scan_ok")
