"""
Local HTTP server for the web UI's <video> and <img> tags.

The page can't read local files directly, so media is served from
127.0.0.1 on a random port. Every URL carries a per-session token, and only
files under the allowed roots (captures folder, clips folder, thumbnail
cache) are served. Range requests are supported so videos can seek.
"""

import mimetypes
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

_CHUNK = 1 << 20
_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")

mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("image/webp", ".webp")


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:      # different drives on Windows
        return False


class MediaServer:
    """`roots()` returns the folders that may be served. It's called per
    request, so a changed captures or clips folder takes effect at once."""

    def __init__(self, roots):
        self._roots = roots
        self.token = secrets.token_urlsafe(16)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def start(self):
        threading.Thread(target=self._httpd.serve_forever, name="media-server", daemon=True).start()
        return self

    def stop(self):
        self._httpd.shutdown()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}/f?t={self.token}&p={quote(os.path.abspath(path))}"

    def allowed(self, path: str) -> bool:
        path = os.path.normcase(os.path.realpath(path))
        return any(_inside(path, os.path.normcase(os.path.realpath(r)))
                   for r in self._roots() if r)

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self._serve(body=False)

            def do_GET(self):
                self._serve(body=True)

            def _serve(self, body):
                url = urlparse(self.path)
                q = parse_qs(url.query)
                if url.path != "/f" or q.get("t", [""])[0] != server.token:
                    return self.send_error(403)
                path = q.get("p", [""])[0]
                if not path or not server.allowed(path) or not os.path.isfile(path):
                    return self.send_error(404)

                size = os.path.getsize(path)
                start, end = 0, size - 1
                m = _RANGE.match(self.headers.get("Range", ""))
                if m and (m[1] or m[2]):
                    if m[1]:
                        start = int(m[1])
                        end = min(int(m[2]), size - 1) if m[2] else size - 1
                    else:               # suffix range: the last N bytes
                        start = max(0, size - int(m[2]))
                    if start > end or start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.end_headers()
                        return
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                else:
                    self.send_response(200)
                length = end - start + 1
                self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if not body:
                    return
                try:
                    with open(path, "rb") as f:
                        f.seek(start)
                        while length > 0:
                            chunk = f.read(min(_CHUNK, length))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            length -= len(chunk)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass    # the player cancels requests all the time when seeking

        return Handler
