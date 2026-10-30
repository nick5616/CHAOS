"""
The methods the page can call, as `await window.pywebview.api.<name>(...)`.

pywebview runs every call on its own thread, so shared state is guarded by
`_lock`. Anything slow runs in a background thread and reports through
events instead of blocking the call. Only underscore names are private:
pywebview exposes every other attribute to JavaScript.
"""

import collections
import errno
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.error

from desktop_app.web import clips, highlights, settings
from desktop_app.web.events import Events
from desktop_app.web.run import RunController

LOW_SPACE_BYTES = 5_000_000_000


def _model_id(model) -> str:
    return os.path.basename(model.path)


def _classify(exc: Exception) -> tuple[str, str]:
    """(kind, message) for a failed model download."""
    if isinstance(exc, urllib.error.HTTPError):
        return "server", f"The download server answered with an error (HTTP {exc.code}). Try again in a bit."
    if isinstance(exc, (urllib.error.URLError, ConnectionError, TimeoutError)):
        return "offline", "Couldn't reach the download server. Check your internet connection and try again."
    if isinstance(exc, RuntimeError) and "checksum" in str(exc):
        return "checksum", "A download came through damaged, so it was thrown away. Trying again usually fixes it."
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return "disk", "The disk is full. Free up some space and try again."
    return "other", str(exc) or exc.__class__.__name__


class Api:
    def __init__(self, config_manager, events: Events, media, dev: bool = False):
        self._config_manager = config_manager
        self._events = events
        self._media = media
        self._dev = dev
        self._lock = threading.Lock()
        self._config_lock = threading.Lock()

        self._models_checked = threading.Event()
        self._models = []               # chaos_lib.models.Model, everything the config needs
        self._models_error = None
        self._downloading = False

        self._gpu = None                # latest detection, None while checking
        self._window = None             # set by main once the window exists

        self._thumbs = clips.Thumbnails(self._thumbs_folder, media, events)
        self._run = RunController(str(config_manager.config_path), events)
        self._cuda_installing = False
        self._exporting = False

    def _start(self):
        """Kick off the slow startup checks. Called before the window opens,
        so they overlap with WebView2 starting up."""
        threading.Thread(target=self._check_models, name="models-check", daemon=True).start()
        threading.Thread(target=self._check_gpu, name="gpu-check", daemon=True).start()

    # ------------------------------------------------------------------ app

    def app_info(self):
        return {"version": "1.0.0", "dev": self._dev, "platform": platform.system().lower()}

    def _config(self) -> dict:
        with self._config_lock:
            return self._config_manager.load_config()

    # ------------------------------------------------------------------ models

    def _check_models(self):
        try:
            from chaos_lib import models
            config = self._config()
            config["data_folder"] = self._config_manager.resolve_path(config["data_folder"])
            found = models.required(config)
            with self._lock:
                self._models, self._models_error = found, None
        except Exception as e:      # a broken install shouldn't hang the launch screen
            with self._lock:
                self._models, self._models_error = [], str(e)
        self._models_checked.set()

    def models_status(self, refresh=False):
        """Every model the current config needs and whether it's on disk.
        Waits for the startup check if it's still running. `refresh` looks
        again, for after settings that change which models are needed."""
        self._models_checked.wait()
        if refresh:
            self._check_models()
        with self._lock:
            return {
                "models": [{"id": _model_id(m), "label": m.label, "mb": m.approx_mb, "ready": m.ready()}
                           for m in self._models],
                "error": self._models_error,
            }

    def download_models(self):
        """Start downloading every missing model. Progress arrives as
        `models:progress`, then `models:done` or `models:error`."""
        self._models_checked.wait()
        with self._lock:
            if self._downloading:
                return {"started": False}
            todo = [m for m in self._models if not m.ready()]
            self._downloading = True
        threading.Thread(target=self._download, args=(todo,), name="models-download", daemon=True).start()
        return {"started": True}

    def _download(self, todo):
        from chaos_lib import models
        sizes = {_model_id(m): m.approx_mb << 20 for m in todo}
        finished = 0                    # bytes in models already done
        samples = collections.deque()   # (time, overall bytes) over the last few seconds
        current = None
        try:
            for m in todo:
                current = mid = _model_id(m)

                def report(state, done, mid=mid):
                    overall_total = sum(sizes.values())
                    overall_done = finished + done
                    now = time.monotonic()
                    samples.append((now, overall_done))
                    while len(samples) > 2 and now - samples[0][0] > 3:
                        samples.popleft()
                    t0, b0 = samples[0]
                    speed = (overall_done - b0) / (now - t0) if now - t0 > 0.25 else 0
                    eta = (overall_total - overall_done) / speed if speed > 0 else None
                    self._events.emit("models:progress", {
                        "id": mid, "state": state, "done": done, "total": sizes[mid],
                        "overall_done": overall_done, "overall_total": overall_total,
                        "bytes_per_sec": round(speed), "eta_sec": eta,
                    }, key=mid)

                def progress(done, total, mid=mid):
                    sizes[mid] = max(total, done)
                    report("downloading", done)

                report("downloading", 0)
                models.fetch(m, progress, verifying=lambda: report("verifying", sizes[mid]))
                report("done", sizes[mid])
                finished += sizes[mid]
            outcome = ("models:done", {})
        except Exception as e:
            kind, message = _classify(e)
            outcome = ("models:error", {"id": current, "kind": kind, "message": message})
        # Clear the flag first, so a Retry clicked the moment the error shows is accepted.
        with self._lock:
            self._downloading = False
        self._events.emit(*outcome)

    # ------------------------------------------------------------------ system

    def _check_gpu(self):
        from desktop_app.gui.utils.system_detector import SystemDetector
        info = {"cuda_available": False, "gpu_present": False, "gpu_name": None,
                "driver_version": None, "max_cuda_version": None}
        try:
            import torch
            if torch.cuda.is_available():
                info.update(cuda_available=True, gpu_present=True, gpu_name=torch.cuda.get_device_name(0))
            else:
                gpu = SystemDetector.detect_nvidia_gpu()
                info.update(gpu_present=gpu.get("present", False), gpu_name=gpu.get("name"),
                            driver_version=gpu.get("driver_version"),
                            max_cuda_version=gpu.get("max_cuda_version"))
        except Exception:
            pass
        try:
            with self._config_lock:
                config = self._config_manager.load_config()
                system = config.setdefault("system", {})
                system["cuda_available"] = info["cuda_available"]
                system["gpu_present"] = info["gpu_present"]
                system["gpu_name"] = info["gpu_name"]
                system["nvidia_driver_version"] = info["driver_version"]
                system["nvidia_max_cuda_version"] = info["max_cuda_version"]
                self._config_manager.save_config(config)
        except Exception:
            pass
        with self._lock:
            self._gpu = info
        self._events.emit("system:gpu", info)

    def gpu_info(self):
        """The startup GPU check's result, or the last one saved in config
        (with `checking: true`) while it's still running."""
        with self._lock:
            if self._gpu is not None:
                return {**self._gpu, "checking": False}
        system = self._config().get("system", {})
        return {"cuda_available": bool(system.get("cuda_available")),
                "gpu_present": bool(system.get("gpu_present")),
                "gpu_name": system.get("gpu_name"),
                "driver_version": system.get("nvidia_driver_version"),
                "max_cuda_version": system.get("nvidia_max_cuda_version"),
                "checking": True}

    # ------------------------------------------------------------------ appearance

    def ui_prefs(self):
        """Look-and-feel settings, kept in config.yaml's gui section (the web
        window doesn't keep browser storage between launches)."""
        gui = self._config().get("gui", {})
        return {"background": gui.get("background", True),
                "background_motion": gui.get("background_motion", True)}

    def set_ui_prefs(self, prefs):
        with self._config_lock:
            config = self._config_manager.load_config()
            gui = config.setdefault("gui", {})
            for key in ("background", "background_motion"):
                if key in prefs:
                    gui[key] = bool(prefs[key])
            self._config_manager.save_config(config)
        return self.ui_prefs()

    # ------------------------------------------------------------------ settings

    def settings_get(self):
        config = self._config()
        return {
            "values": settings.read(config),
            "defaults": settings.read(self._config_manager.default_config),
            "resolved": {k: self._config_manager.resolve_path(config.get(k) or "")
                         for k in ("data_folder", "final_clips_folder")},
        }

    def settings_set(self, patch):
        """Change settings (dotted keys, see web/settings.py). Returns the
        new settings, or {"error": ...} if a value was rejected."""
        try:
            with self._config_lock:
                config = self._config_manager.load_config()
                settings.apply(config, dict(patch))
                if not self._config_manager.save_config(config):
                    return {"error": "Couldn't write config.yaml."}
        except (ValueError, TypeError) as e:
            return {"error": str(e)}
        return self.settings_get()

    def settings_reset_tuning(self):
        defaults = settings.read(self._config_manager.default_config)
        return self.settings_set({k: defaults[k] for k in settings.TUNING_KEYS if defaults[k] is not None})

    def choose_setting_folder(self, key):
        if key not in ("captures_folder", "data_folder", "final_clips_folder"):
            return {"error": f"Not a folder setting: {key}"}
        folder = self._pick_folder(self._resolved(key) if key != "captures_folder" else self._config().get(key) or "")
        if not folder:
            return None
        result = self.settings_set({key: folder})
        if key == "captures_folder":
            self._thumbs.forget_queue()
        return result

    # ------------------------------------------------------------------ setup

    def system_check(self):
        from desktop_app.gui.utils.system_detector import SystemDetector
        py_ok, py_version = SystemDetector.check_python_version()
        ff_ok, ff_info = SystemDetector.check_ffmpeg()
        return {"python": {"ok": py_ok, "detail": py_version},
                "ffmpeg": {"ok": ff_ok, "detail": (ff_info or "").splitlines()[0][:80] if ff_info else ""},
                "setup_complete": bool(self._config().get("gui", {}).get("setup_complete"))}

    def _recordings(self):
        folder = self._config().get("captures_folder") or ""
        return clips.list_videos(folder) if folder and os.path.isdir(folder) else []

    def detect_resolution(self):
        """Width and height of the newest recording, to pick a preset."""
        videos = self._recordings()
        if not videos:
            return None
        from desktop_app.web import export
        w, h = export._probe(videos[0]["path"])["size"]
        return [w, h]

    def roi_frame(self, index=0, fraction=0.35):
        """A full-size frame from the index-th newest recording, for drawing
        the killfeed region on. Cached next to the thumbnails."""
        videos = self._recordings()
        if not videos:
            return None
        index = max(0, min(int(index), len(videos) - 1))
        path = videos[index]["path"]
        from chaos_lib.clipper import _get_ffmpeg
        from desktop_app.web import export
        probe = export._probe(path)
        t = max(0.0, min(1.0, float(fraction))) * probe["duration"]
        folder = os.path.join(self._thumbs_folder(), "frames")
        os.makedirs(folder, exist_ok=True)
        key = clips.Thumbnails._key(path) or "x"
        out = os.path.join(folder, f"{key}_{int(t * 10)}.jpg")
        if not os.path.exists(out):
            subprocess.run([_get_ffmpeg(), "-hide_banner", "-y", "-ss", f"{t:.2f}", "-i", path,
                            "-frames:v", "1", "-q:v", "3", out], capture_output=True, timeout=60)
        if not os.path.exists(out):
            return None
        w, h = probe["size"]
        return {"url": self._media.url(out), "width": w, "height": h, "name": videos[index]["name"],
                "recorded": videos[index]["recorded"], "t": t, "duration": probe["duration"],
                "index": index, "count": min(len(videos), 25)}

    # ------------------------------------------------------------------ folders

    def _resolved(self, key: str) -> str:
        return self._config_manager.resolve_path(self._config().get(key) or "")

    def _thumbs_folder(self) -> str:
        return os.path.join(self._resolved("data_folder"), "thumbnails")

    def _set_config(self, **values):
        with self._config_lock:
            config = self._config_manager.load_config()
            config.update(values)
            self._config_manager.save_config(config)

    def _pick_folder(self, start: str):
        import webview
        picked = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=start or "")
        return picked[0] if picked else None

    def _open_folder(self, folder: str):
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])

    # ------------------------------------------------------------------ clips screen

    def list_clips(self):
        """The captures folder and the videos in it, newest first."""
        folder = self._config().get("captures_folder") or ""
        exists = bool(folder) and os.path.isdir(folder)
        videos = [dict(v, url=self._media.url(v["path"])) for v in clips.list_videos(folder)] if exists else []
        return {"folder": folder, "exists": exists, "videos": videos}

    def choose_captures_folder(self):
        folder = self._pick_folder(self._config().get("captures_folder") or "")
        if not folder:
            return None
        self._thumbs.forget_queue()
        self._set_config(captures_folder=folder)
        return self.list_clips()

    def request_thumbnails(self, paths):
        """Cached thumbnails now; the rest arrive as `clips:thumb` events."""
        return self._thumbs.request(list(paths))

    def open_captures_folder(self):
        folder = self._config().get("captures_folder")
        if folder and os.path.isdir(folder):
            self._open_folder(folder)

    # ------------------------------------------------------------------ highlights

    def highlights(self):
        """The last run's highlights, best first, with their clip files."""
        return highlights.load(self._resolved("data_folder"), self._resolved("final_clips_folder"), self._media)

    def reveal_file(self, path):
        """Open Explorer (Finder...) with the file selected."""
        if not path or not os.path.isfile(path) or not self._media.allowed(path):
            return False
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return True

    def export_sequence(self, paths):
        """Ask where to save, then stitch `paths` in order. Progress comes as
        `export:progress` {fraction}, then `export:done` {ok, path, mode, message}."""
        import webview
        paths = [p for p in paths if os.path.isfile(p) and self._media.allowed(p)]
        if not paths:
            return False
        with self._lock:
            if self._exporting:
                return False
        picked = self._window.create_file_dialog(
            webview.FileDialog.SAVE, directory=self._resolved("final_clips_folder"),
            save_filename="chaos_highlights.mp4", file_types=("MP4 video (*.mp4)",))
        if not picked:
            return False
        out = picked if isinstance(picked, str) else picked[0]
        if not out.lower().endswith(".mp4"):
            out += ".mp4"
        with self._lock:
            self._exporting = True
        threading.Thread(target=self._export, args=(paths, out), name="export", daemon=True).start()
        return True

    def _export(self, paths, out):
        from desktop_app.web import export
        try:
            mode = export.stitch(paths, out, lambda f: self._events.emit("export:progress", {"fraction": f}))
            result = {"ok": True, "path": out, "mode": mode, "message": ""}
        except Exception as e:
            result = {"ok": False, "path": out, "mode": None, "message": str(e)[-800:]}
        with self._lock:
            self._exporting = False
        self._events.emit("export:done", result)

    # ------------------------------------------------------------------ run setup

    def run_setup(self):
        config = self._config()
        out = self._resolved("final_clips_folder")
        free = clips.free_bytes(out)
        names = config.get("player_names") or []
        workers = config.get("pipeline", {}).get("analysis_workers", config.get("analysis_workers", "auto"))
        return {
            "player_names": [n for n in names if isinstance(n, str)] if isinstance(names, list) else [str(names)],
            "clips_folder": out,
            "free_bytes": free,
            "low_space": free is not None and free < LOW_SPACE_BYTES,
            "workers": workers if isinstance(workers, int) and workers > 0 else None,
        }

    def worker_plan(self):
        from chaos_lib.resources import plan_analysis_workers
        plan = plan_analysis_workers(self._config())
        return {"device": plan.device, "workers": plan.workers, "max_workers": plan.max_workers,
                "summary": plan.summary}

    def save_player_names(self, names):
        clean = [n.strip() for n in names if isinstance(n, str) and n.strip()]
        self._set_config(player_names=clean)
        return clean

    def choose_clips_folder(self):
        folder = self._pick_folder(self._resolved("final_clips_folder"))
        if folder:
            self._set_config(final_clips_folder=folder)
        return self.run_setup()

    def open_clips_folder(self):
        self._open_folder(self._resolved("final_clips_folder"))

    # ------------------------------------------------------------------ run

    def start_run(self, paths, workers=None):
        """Start a run over `paths`. Refuses if one is running or a model is
        missing (the page then shows the download screen and tries again)."""
        paths = [p for p in paths if os.path.isfile(p)]
        if not paths:
            return {"ok": False, "error": "no_videos"}
        from chaos_lib import models
        config = self._config()
        config["data_folder"] = self._config_manager.resolve_path(config["data_folder"])
        needed = models.required(config)
        if any(not m.ready() for m in needed):
            with self._lock:
                self._models = needed
            return {"ok": False, "error": "models_missing"}
        if not self._run.start(paths, workers if isinstance(workers, int) and workers > 0 else None):
            return {"ok": False, "error": "running"}
        return {"ok": True}

    def stop_run(self):
        self._run.stop()

    def set_run_workers(self, n):
        self._run.set_workers(n)

    def set_gaming(self, on):
        self._run.set_gaming(on)

    def run_snapshot(self):
        return self._run.snapshot()

    def export_log(self, text):
        import webview
        picked = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename="chaos-run-log.txt")
        if not picked:
            return False
        path = picked if isinstance(picked, str) else picked[0]
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True

    # ------------------------------------------------------------------ CUDA

    def cuda_install_command(self):
        from desktop_app.gui.utils.system_detector import SystemDetector
        system = self._config().get("system", {})
        return SystemDetector.get_pytorch_install_command(system.get("nvidia_max_cuda_version"))

    def install_cuda(self):
        """pip-install the CUDA build of PyTorch. Output streams as
        `cuda:output`, then `cuda:done` with {success}."""
        with self._lock:
            if self._cuda_installing:
                return False
            self._cuda_installing = True
        threading.Thread(target=self._install_cuda, args=(self.cuda_install_command(),),
                         name="cuda-install", daemon=True).start()
        return True

    def _install_cuda(self, command: str):
        args = command.split()
        if args[:1] == ["pip"]:
            # The interpreter CHAOS runs under, so it lands in the right environment.
            args = [sys.executable, "-m", "pip"] + args[1:]
        ok = False
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, errors="replace")
            for line in proc.stdout:
                self._events.emit("cuda:output", {"line": line.rstrip()})
            ok = proc.wait() == 0
        except Exception as e:
            self._events.emit("cuda:output", {"line": f"Error: {e}"})
        with self._lock:
            self._cuda_installing = False
        self._events.emit("cuda:done", {"success": ok})

    def restart_app(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        subprocess.Popen([sys.executable, os.path.join(root, "run_desktop_app.py"), "--web"], cwd=root)
        self._window.destroy()
