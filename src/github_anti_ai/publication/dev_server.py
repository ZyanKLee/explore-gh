"""Local preview: serves the built site and rebuilds it when an edition or the theme changes.

The browser reloads by itself. The script for that is added while a page is served,
the built files stay free of scripts.
"""

import sys
import threading
import time
from collections.abc import Callable, Sequence
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RELOAD_PATH = "/__version"
HOST = "127.0.0.1"  # the preview is for this computer only
POLL_SECONDS = 0.5

_RELOAD_SCRIPT = (
    b"<script>(function(){var seen=null;setInterval(function(){"
    b"fetch('" + RELOAD_PATH.encode() + b"',{cache:'no-store'})"
    b".then(function(r){return r.text()})"
    b".then(function(v){if(seen===null){seen=v}else if(v!==seen){location.reload()}})"
    b".catch(function(){})},1000)})()</script>"
)


class Watcher:
    """Notices when files below the watched directories are added, edited or deleted."""

    def __init__(self, directories: Sequence[Path]):
        self._directories = [Path(directory) for directory in directories]
        self._seen = self._look()

    def changed(self) -> bool:
        now = self._look()
        if now == self._seen:
            return False
        self._seen = now
        return True

    def _look(self) -> dict[Path, tuple[int, int]]:
        found = {}
        for directory in self._directories:
            for path in directory.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    stat = path.stat()
                    found[path] = (stat.st_mtime_ns, stat.st_size)
        return found


class Preview:
    """Builds at the start and again after each change. The version tells the browser."""

    def __init__(self, build: Callable[[], None], watcher: Watcher):
        self._build = build
        self._watcher = watcher
        self.version = 0
        self._build()
        self.version = 1

    def refresh(self) -> bool:
        """Rebuilds if something changed. A build that fails keeps the last pages."""
        if not self._watcher.changed():
            return False
        try:
            self._build()
        except Exception as error:  # whatever goes wrong, the preview must keep running
            print(f"Fehler beim Bauen: {error}", file=sys.stderr)
            return False
        self.version += 1
        return True


def with_reload_script(page: bytes) -> bytes:
    position = page.rfind(b"</body>")
    if position < 0:
        return page
    return page[:position] + _RELOAD_SCRIPT + page[position:]


class _Handler(SimpleHTTPRequestHandler):
    version_of_site: Callable[[], int]

    def do_GET(self):
        if self.path.split("?")[0] == RELOAD_PATH:
            self._send(str(self.version_of_site()).encode(), "text/plain; charset=utf-8")
            return
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            if not self.path.split("?")[0].endswith("/"):
                return super().do_GET()  # redirects to the address with a slash
            path = path / "index.html"
        if path.suffix == ".html" and path.is_file():
            self._send(with_reload_script(path.read_bytes()), "text/html; charset=utf-8")
            return
        super().do_GET()

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # one line per request would bury the build messages


def make_server(
    output_dir: Path, port: int, version: Callable[[], int]
) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"version_of_site": staticmethod(version)})
    return ThreadingHTTPServer((HOST, port), partial(handler, directory=str(output_dir)))


def serve(build: Callable[[], None], watch: Sequence[Path], output_dir: Path, port: int) -> None:
    """Runs until interrupted with Ctrl+C."""
    preview = Preview(build, Watcher(watch))
    server = make_server(output_dir, port, version=lambda: preview.version)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(
        f"Vorschau läuft: http://{HOST}:{server.server_address[1]}/   (Strg+C beendet)", flush=True
    )
    try:
        while True:
            time.sleep(POLL_SECONDS)
            if preview.refresh():
                print(f"{time.strftime('%H:%M:%S')} Änderung erkannt, Seite neu gebaut", flush=True)
    except KeyboardInterrupt:
        print("\nVorschau beendet")
    finally:
        server.shutdown()
        server.server_close()
