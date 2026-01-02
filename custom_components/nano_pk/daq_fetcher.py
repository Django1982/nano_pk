"""Utility helpers for fetching DAQPRJ templates via telnet."""

from __future__ import annotations

import asyncio
import re
from typing import Optional

DEFAULT_COMMAND = "$DAQ DESC"
_DAQ_PATTERN = re.compile(r"<DAQPRJ[\s\S]+?</DAQPRJ>", re.IGNORECASE)
_PM_LINE_RE = re.compile(r"\npm [^\n]*")


def _clean_telnet_noise(text: str) -> str:
    """Remove prompt markers injected into the DAQ response."""
    text = text.replace(">>>", ">").replace("$<<<", "<")
    return _PM_LINE_RE.sub("\n", text)


class DaqFetchError(RuntimeError):
    """Raised when fetching the DAQ template fails."""


async def async_fetch_daq_template(
    host: str,
    port: int = 23,
    command: str = DEFAULT_COMMAND,
    connect_timeout: float = 8.0,
    read_timeout: float = 5.0,
) -> str:
    """Fetch the DAQPRJ XML definition from a boiler via telnet."""
    message = command.strip().encode("ascii") + b"\r\n"

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=connect_timeout
        )
    except Exception as exc:
        raise DaqFetchError(f"Failed to open telnet connection: {exc}") from exc

    try:
        writer.write(message)
        await writer.drain()

        try:
            payload = await asyncio.wait_for(
                reader.readuntil(b"</DAQPRJ>"), timeout=read_timeout
            )
        except asyncio.IncompleteReadError as exc:
            payload = exc.partial
            raise DaqFetchError("DAQPRJ stream ended before closing tag") from exc
        except Exception as exc:
            raise DaqFetchError(f"Failed to read DAQPRJ response: {exc}") from exc
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    response = _clean_telnet_noise(payload.decode("latin-1", errors="ignore"))

    match = _DAQ_PATTERN.search(response)
    if not match:
        raise DaqFetchError("No <DAQPRJ> block found in response")
    return match.group(0)


def fetch_daq_template(
    host: str,
    port: int = 23,
    command: str = DEFAULT_COMMAND,
    connect_timeout: float = 8.0,
    read_timeout: float = 5.0,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> str:
    """Synchronous helper for CLI usage."""
    coro = async_fetch_daq_template(
        host=host,
        port=port,
        command=command,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
    if loop:
        return loop.run_until_complete(coro)
    return asyncio.run(coro)
