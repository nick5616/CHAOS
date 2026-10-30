"""
Push events from Python to the page.

`emit(name, payload)` dispatches `CustomEvent("chaos", {detail: {name, payload}})`
on the page's window. Progress-style events are coalesced to about ten a
second (only the latest payload per key is sent); any other event flushes
those first, so a "done" never arrives ahead of the last progress update.
"""

import json
import threading

THROTTLED = {"models:progress", "run:progress", "run:job", "export:progress"}
_INTERVAL = 0.1


class Events:
    def __init__(self):
        self._window = None
        self._lock = threading.Lock()       # one run_js at a time, in emit order
        self._pending = {}                  # (name, key) -> payload
        self._timer = None

    def attach(self, window):
        self._window = window

    def emit(self, name: str, payload=None, key=None):
        if name in THROTTLED:
            with self._lock:
                self._pending[(name, key)] = payload
                if self._timer is None:
                    self._timer = threading.Timer(_INTERVAL, self.flush)
                    self._timer.daemon = True
                    self._timer.start()
            return
        with self._lock:
            self._flush_locked()
            self._send(name, payload)

    def flush(self):
        with self._lock:
            self._flush_locked()

    def _flush_locked(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        pending, self._pending = self._pending, {}
        for (name, _), payload in pending.items():
            self._send(name, payload)

    def _send(self, name, payload):
        if self._window is None:
            return
        detail = json.dumps({"name": name, "payload": payload})
        try:
            self._window.run_js(f"window.dispatchEvent(new CustomEvent('chaos', {{detail: {detail}}}))")
        except Exception:
            pass    # window closing
