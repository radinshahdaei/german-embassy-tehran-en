from __future__ import annotations

import http.server
import socketserver
from functools import partial
from pathlib import Path


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"[server] {self.address_string()} - {format % args}")


def serve(directory: Path, host: str, port: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    handler = partial(QuietHandler, directory=str(directory))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((host, port), handler) as server:
        print(f"English mirror: http://localhost:{port}")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
