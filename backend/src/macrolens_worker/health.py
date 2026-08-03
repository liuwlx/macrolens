from __future__ import annotations

import asyncio
import os
from contextlib import suppress

from macrolens_api.logging import get_logger

logger = get_logger(__name__)


async def health_server(role: str) -> None:
    """Expose the HTTP port required by Cloud Run while background loops do the work."""

    port = int(os.getenv("PORT", "8080"))

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with suppress(Exception):
            await reader.readuntil(b"\r\n\r\n")
        body = f'{{"status":"ok","role":"{role}"}}'.encode()
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Cache-Control: no-store\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, host="0.0.0.0", port=port)
    logger.info("worker_health_server_started", role=role, port=port)
    async with server:
        await server.serve_forever()
