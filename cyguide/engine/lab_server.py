"""Lightweight embedded asyncio mock target server for offline student practice."""

import asyncio
import json
import logging
from http import HTTPStatus
from typing import Optional

logger = logging.getLogger("cyguide.lab_server")


class LabMockServer:
    """Hermetic local web target simulating endpoints, headers, and vulnerabilities.

    Provides a 100% legal, offline loopback practice target for nmap, ffuf, nuclei, and nikto.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8888) -> None:
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None

    async def start(self) -> None:
        """Start the loopback TCP server."""
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)

    async def serve_forever(self) -> None:
        """Run the server until interrupted."""
        if not self.server:
            await self.start()
        assert self.server is not None
        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Close server sockets."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Parse minimal HTTP/1.1 requests and return simulated responses."""
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            request_line = line.decode("utf-8", errors="replace").strip()
            parts = request_line.split()
            if len(parts) < 2:
                writer.close()
                await writer.wait_closed()
                return

            method, path = parts[0].upper(), parts[1]

            # Read headers until empty line
            headers = {}
            while True:
                hdr_line = await reader.readline()
                if not hdr_line or hdr_line in (b"\r\n", b"\n"):
                    break
                decoded_hdr = hdr_line.decode("utf-8", errors="replace").strip()
                if ":" in decoded_hdr:
                    k, v = decoded_hdr.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            status_code, content_type, body_bytes = self._route_request(method, path, headers)

            response = (
                f"HTTP/1.1 {status_code} {HTTPStatus(status_code).phrase}\r\n"
                f"Server: CyGuide-MockLab/1.0 (Embedded-Target)\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                f"Connection: close\r\n"
                f"X-Powered-By: CyGuide-Practice-Framework\r\n"
                f"\r\n"
            ).encode("utf-8") + body_bytes

            writer.write(response)
            await writer.drain()
        except Exception as exc:
            logger.debug("Lab mock server connection error: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _route_request(self, method: str, path: str, headers: dict) -> tuple[int, str, bytes]:
        """Route URI path to simulated responses."""
        # Normalize path query
        raw_path = path.split("?")[0].rstrip("/") or "/"

        if raw_path == "/":
            body = (
                "<!DOCTYPE html>\n"
                "<html>\n"
                "<head><title>CyGuide Practice Lab Target</title></head>\n"
                "<body>\n"
                "  <h1>CyGuide Local Target Portal</h1>\n"
                "  <p>Status: Online | Environment: Hermetic Loopback Sandbox</p>\n"
                "  <!-- Notice: Check /robots.txt for restricted areas -->\n"
                "</body>\n"
                "</html>\n"
            )
            return 200, "text/html", body.encode("utf-8")

        elif raw_path == "/robots.txt":
            body = (
                "User-agent: *\nDisallow: /admin\nDisallow: /api/internal\nDisallow: /backup.zip\n"
            )
            return 200, "text/plain", body.encode("utf-8")

        elif raw_path == "/admin":
            body = (
                "<!DOCTYPE html><html><body>"
                "<h1>403 Forbidden</h1>"
                "<p>Administrative console restricted to internal subnet.</p>"
                "</body></html>"
            )
            return 403, "text/html", body.encode("utf-8")

        elif raw_path == "/api/version":
            data = {
                "service": "cyguide-lab-portal",
                "version": "1.0.4",
                "framework": "express/4.17.1",
                "environment": "offline-practice",
            }
            return 200, "application/json", json.dumps(data).encode("utf-8")

        elif raw_path == "/login":
            body = (
                "<!DOCTYPE html><html><body>\n"
                "<h2>Portal Sign In</h2>\n"
                "<form method='POST'>\n"
                "  <input type='text' name='username' placeholder='Username' />\n"
                "  <input type='password' name='password' placeholder='Password' />\n"
                "  <button type='submit'>Login</button>\n"
                "</form>\n"
                "</body></html>"
            )
            return 200, "text/html", body.encode("utf-8")

        elif raw_path in ("/api/internal", "/backup.zip"):
            body = "Protected asset."
            return 401, "text/plain", body.encode("utf-8")

        else:
            body = "<!DOCTYPE html><html><body><h1>404 Not Found</h1></body></html>"
            return 404, "text/html", body.encode("utf-8")
