"""Zero-dependency local HTTP server for Chronos Web UI."""

from __future__ import annotations
import json
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from chronos.storage import ChronosStore

WEB_DIR = Path(__file__).parent / "web"


class ChronosRequestHandler(BaseHTTPRequestHandler):
    store: ChronosStore

    def log_message(self, format, *args):
        # Suppress routine log clutter
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_file(WEB_DIR / "index.html", "text/html")
        elif path == "/api/runs":
            runs = self.store.list_runs()
            self._serve_json(runs)
        elif path.startswith("/api/runs/"):
            run_id = path.split("/api/runs/")[1].strip("/")
            graph = self.store.get_run_graph(run_id)
            if not graph:
                self._send_error(404, f"Run '{run_id}' not found")
            else:
                self._serve_json(graph)
        elif path.startswith("/api/checkpoints/"):
            chk_id = path.split("/api/checkpoints/")[1].strip("/")
            chk = self.store.get_checkpoint(chk_id)
            if not chk:
                self._send_error(404, f"Checkpoint '{chk_id}' not found")
            else:
                self._serve_json(chk.to_dict())
        else:
            self._send_error(404, "Endpoint Not Found")

    def _serve_file(self, filepath: Path, content_type: str):
        if not filepath.exists():
            self._send_error(404, f"File {filepath.name} not found")
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(
    host: str = "127.0.0.1",
    port: int = 4040,
    db_path: str = ".chronos.db",
    open_browser: bool = False
):
    """Start the Chronos UI web server."""
    ChronosRequestHandler.store = ChronosStore(db_path=db_path)
    server = ThreadingHTTPServer((host, port), ChronosRequestHandler)
    url = f"http://{host}:{port}"
    print(f"\n⏳ Chronos Web UI running at: {url}")
    print(f"📁 Tracking Database: {db_path}")
    print("Press Ctrl+C to stop.\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Chronos Web UI.")
        server.server_close()
