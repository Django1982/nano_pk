"""Helpers to retrieve the DAQ descriptor from a Hargassner boiler."""

from __future__ import annotations

import asyncio
import logging
from typing import Final

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT: Final[int] = 23
DEFAULT_COMMAND: Final[str] = "$DAQ DESC\r\n"
DEFAULT_TOTAL_TIMEOUT: Final[float] = 10.0
DEFAULT_CHUNK_TIMEOUT: Final[float] = 1.0
DEFAULT_MAX_BYTES: Final[int] = 256_000


class DescriptorError(Exception):
    """Base error for descriptor fetching."""


class DescriptorConnectionError(DescriptorError):
    """Unable to open the TCP connection."""


class DescriptorTimeout(DescriptorError):
    """Timeout while fetching the descriptor."""


class DescriptorFormatError(DescriptorError):
    """Descriptor payload could not be normalised."""


async def async_fetch_descriptor(
    host: str,
    *,
    port: int = DEFAULT_PORT,
    command: str = DEFAULT_COMMAND,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    chunk_timeout: float = DEFAULT_CHUNK_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> str:
    """Fetch the `$DAQ DESC` descriptor from the boiler.

    Returns the descriptor as a normalised XML string decoded with latin-1.
    """

    loop = asyncio.get_running_loop()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=total_timeout,
        )
    except asyncio.TimeoutError as exc:  # Connection attempt timed out
        raise DescriptorTimeout(f"Timeout connecting to {host}:{port}") from exc
    except OSError as exc:  # Network failure
        raise DescriptorConnectionError(f"Failed to connect to {host}:{port}: {exc}") from exc

    try:
        writer.write(command.encode("ascii"))
        await asyncio.wait_for(writer.drain(), timeout=min(2.0, total_timeout))

        buffer = bytearray()
        deadline = loop.time() + total_timeout
        closing_tag = b"</DAQPRJ>"

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise DescriptorTimeout("Timed out waiting for descriptor payload")

            try:
                chunk = await asyncio.wait_for(
                    reader.read(4096),
                    timeout=min(chunk_timeout, remaining),
                )
            except asyncio.TimeoutError as exc:
                raise DescriptorTimeout("Timed out while reading descriptor data") from exc

            if not chunk:
                break

            buffer.extend(chunk)

            if closing_tag in buffer:
                break

            if len(buffer) > max_bytes:
                raise DescriptorFormatError("Descriptor response exceeded maximum allowed size")

        end_index = buffer.find(closing_tag)
        if end_index == -1:
            raise DescriptorFormatError("Descriptor response missing closing </DAQPRJ> tag")

        descriptor_bytes = buffer[: end_index + len(closing_tag)]
        descriptor = _normalise_descriptor(descriptor_bytes)

        _LOGGER.debug(
            "Fetched DAQ descriptor from %s:%d (%d bytes)",
            host,
            port,
            len(descriptor_bytes),
        )

        return descriptor

    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # Ignore errors while closing the socket
            pass


def _normalise_descriptor(payload: bytes) -> str:
    """Strip transmission markers and decode the descriptor payload."""

    cleaned = payload.replace(b"$<<<", b"<").replace(b">>>", b">")
    cleaned = cleaned.replace(b"\r", b"").strip()

    if not cleaned:
        raise DescriptorFormatError("Descriptor response was empty after normalisation")

    if b"</DAQPRJ>" not in cleaned:
        raise DescriptorFormatError("Descriptor payload does not contain closing </DAQPRJ>")

    # Truncate in case additional data (e.g. pm stream) followed immediately.
    cleaned = cleaned[: cleaned.index(b"</DAQPRJ>") + len(b"</DAQPRJ>")]

    if not cleaned.startswith(b"<"):
        cleaned = b"<" + cleaned

    try:
        return cleaned.decode("latin-1")
    except UnicodeDecodeError as exc:
        raise DescriptorFormatError("Descriptor payload is not valid latin-1") from exc
