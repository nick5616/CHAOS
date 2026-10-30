"""
The captures folder for the Clips screen: list the videos, and make
thumbnails for them on demand.

Thumbnails are JPEGs cut by ffmpeg into <data_folder>/thumbnails, keyed by
path, size and mtime so an edited file gets a fresh one. The same ffmpeg
call reports the duration, which is cached alongside in index.json. The page
asks only for the cards it can see; the newest requests are served first,
so scrolling quickly doesn't leave the visible cards waiting behind ones
that have scrolled away.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi"}
THUMB_WIDTH = 480
_WORKERS = 4
_TITLE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2}) - (\d{2})\.(\d{2})\.(\d{2})")
_DURATION = re.compile(r"Duration: (\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


def recording_time(path: str) -> datetime | None:
    """When ShadowPlay recorded it, from names like
    'Counter-strike 2 2026.10.29 - 00.33.19.09.DVR.mp4'."""
    m = _TITLE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return datetime(*map(int, m.groups()))
    except ValueError:
        return None


def list_videos(folder: str) -> list[dict]:
    """Videos directly in `folder`, newest first."""
    videos = []
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return videos
    for e in entries:
        if not e.is_file() or os.path.splitext(e.name)[1].lower() not in VIDEO_EXTS:
            continue
        st = e.stat()
        when = recording_time(e.path) or datetime.fromtimestamp(st.st_mtime)
        videos.append({"path": e.path, "name": e.name, "size": st.st_size,
                       "recorded": when.isoformat(timespec="seconds")})
    videos.sort(key=lambda v: v["recorded"], reverse=True)
    return videos


class Thumbnails:
    def __init__(self, folder_fn, media, events):
        self._folder_fn = folder_fn     # -> thumbnails folder (follows config changes)
        self._media = media
        self._events = events
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._queue = []                # paths, newest request last
        self._busy = set()
        self._index = None              # key -> duration, loaded lazily
        self._index_folder = None
        for i in range(_WORKERS):
            threading.Thread(target=self._work, name=f"thumbs-{i}", daemon=True).start()

    def request(self, paths: list[str]) -> list[dict]:
        """Thumbnails already cached come straight back; the rest are queued
        and arrive later as `clips:thumb` events."""
        ready = []
        with self._lock:
            self._load_index()
            for p in paths:
                key = self._key(p)
                if key is None:
                    continue
                jpg = os.path.join(self._index_folder, key + ".jpg")
                if key in self._index and os.path.exists(jpg):
                    ready.append({"path": p, "url": self._media.url(jpg), "duration": self._index[key]})
                    continue
                if p in self._queue:
                    self._queue.remove(p)
                if p not in self._busy:
                    self._queue.append(p)
            self._wake.notify_all()
        return ready

    def forget_queue(self):
        """Drop pending work, e.g. when the folder changes."""
        with self._lock:
            self._queue.clear()

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _key(path: str) -> str | None:
        try:
            st = os.stat(path)
        except OSError:
            return None
        raw = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}"
        return hashlib.sha1(raw.encode("utf-8", "surrogatepass")).hexdigest()[:20]

    def _load_index(self):
        folder = self._folder_fn()
        if self._index is not None and folder == self._index_folder:
            return
        self._index_folder = folder
        os.makedirs(folder, exist_ok=True)
        try:
            with open(os.path.join(folder, "index.json"), encoding="utf-8") as f:
                self._index = json.load(f)
        except (OSError, ValueError):
            self._index = {}

    def _save_index(self):
        tmp = os.path.join(self._index_folder, "index.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f)
        os.replace(tmp, os.path.join(self._index_folder, "index.json"))

    def _work(self):
        while True:
            with self._lock:
                while not self._queue:
                    self._wake.wait()
                path = self._queue.pop()        # newest request first
                self._busy.add(path)
                self._load_index()
                folder = self._index_folder
            try:
                result = self._make(path, folder)
            except Exception:
                result = None
            with self._lock:
                self._busy.discard(path)
                if result and folder == self._index_folder:
                    key, duration = result
                    self._index[key] = duration
                    try:
                        self._save_index()
                    except OSError:
                        pass
            if result:
                key, duration = result
                self._events.emit("clips:thumb", {
                    "path": path, "url": self._media.url(os.path.join(folder, key + ".jpg")),
                    "duration": duration})
            else:
                self._events.emit("clips:thumb", {"path": path, "url": None, "duration": None})

    def _make(self, path: str, folder: str):
        key = self._key(path)
        if key is None:
            return None
        from chaos_lib.clipper import _get_ffmpeg
        out = os.path.join(folder, key + ".jpg")
        tmp = out + ".tmp.jpg"
        duration = None
        # A few seconds in skips the black first frames; very short videos
        # fall back to the start.
        for seek in ("4", "0"):
            proc = subprocess.run(
                [_get_ffmpeg(), "-hide_banner", "-y", "-ss", seek, "-i", path, "-frames:v", "1",
                 "-vf", f"scale={THUMB_WIDTH}:-2", "-q:v", "4", tmp],
                capture_output=True, text=True, errors="replace", timeout=60)
            m = _DURATION.search(proc.stderr)
            if m:
                h, mnt, s = m.groups()
                duration = int(h) * 3600 + int(mnt) * 60 + float(s)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, out)
                return key, duration
        if os.path.exists(tmp):
            os.remove(tmp)
        return None


def free_bytes(path: str) -> int | None:
    """Free space on the drive holding `path`, walking up to the nearest
    folder that exists (the clips folder may not be created yet)."""
    p = os.path.abspath(path)
    while not os.path.exists(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return None
