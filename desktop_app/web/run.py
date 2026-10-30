"""
Runs the pipeline for the web UI: PipelineRunner on a background thread,
its channels turned into `run:*` events, and a snapshot of the run kept so
the page can re-sync whenever the Run screen mounts.
"""

import threading
import time

from desktop_app.workers.pipeline import PipelineRunner

_LOG_CAP = 3000
ALL_STAGES = ["ingest", "analyze", "correlate", "clip", "summary"]


class RunController:
    def __init__(self, config_path: str, events):
        self._config_path = config_path
        self._events = events
        self._lock = threading.Lock()
        self._runner = None
        self._gaming = False
        self._state = self._idle_state()

    @staticmethod
    def _idle_state():
        return {"running": False, "started_at": None, "finished": None, "total": 0, "done": 0,
                "workers": None, "jobs": {}, "order": [], "log": []}

    # ------------------------------------------------------------------ api

    def snapshot(self) -> dict:
        with self._lock:
            s = dict(self._state)
            s["jobs"] = {k: dict(v) for k, v in s["jobs"].items()}
            s["order"] = list(s["order"])
            s["log"] = list(s["log"])
            s["gaming"] = self._gaming
            return s

    def start(self, file_list: list[str], requested_workers) -> bool:
        with self._lock:
            if self._state["running"]:
                return False
            self._state = self._idle_state()
            self._state.update(running=True, started_at=time.time(), total=len(file_list))
            runner = PipelineRunner(ALL_STAGES, self._config_path, file_list, requested_workers)
            self._runner = runner
            if self._gaming:
                runner.set_gaming_mode(True)

        runner.log_message.connect(lambda m: self._log("info", m))
        runner.error_occurred.connect(lambda m: self._log("error", m))
        runner.job_started.connect(lambda n, s: self._job(n, stage=s))
        runner.job_updated.connect(lambda n, s: self._job(n, stage=s))
        runner.job_finished.connect(lambda n, ok: self._job(n, stage="done" if ok else "failed"))
        runner.clips_found.connect(lambda n, c: self._job(n, clips=c))
        runner.pipeline_count.connect(self._count)
        runner.workers_count_changed.connect(self._workers)
        runner.finished.connect(self._finished)

        self._events.emit("run:started", self.snapshot())
        threading.Thread(target=runner.run, name="pipeline", daemon=True).start()
        return True

    def stop(self):
        runner = self._runner
        if runner and self._state["running"]:
            runner.stop()

    def set_workers(self, n: int):
        runner = self._runner
        if runner and self._state["running"]:
            runner.set_target_workers(int(n))

    def set_gaming(self, on: bool):
        self._gaming = bool(on)
        runner = self._runner
        if runner and self._state["running"]:
            runner.set_gaming_mode(self._gaming)
        self._events.emit("run:gaming", {"on": self._gaming})

    # ------------------------------------------------------------------ runner channels

    def _log(self, level: str, text: str):
        entry = {"t": time.time(), "level": level, "text": text}
        with self._lock:
            log = self._state["log"]
            log.append(entry)
            if len(log) > _LOG_CAP:
                del log[: len(log) - _LOG_CAP]
        self._events.emit("run:log", entry)

    def _job(self, name: str, **changes):
        with self._lock:
            jobs = self._state["jobs"]
            if name not in jobs:
                jobs[name] = {"name": name, "stage": "queued", "clips": None}
                self._state["order"].append(name)
            jobs[name].update(changes)
            job = dict(jobs[name])
        self._events.emit("run:job", job, key=name)

    def _count(self, done: int, total: int):
        with self._lock:
            self._state.update(done=done, total=total)
        self._events.emit("run:count", {"done": done, "total": total})

    def _workers(self, n: int):
        with self._lock:
            self._state["workers"] = n
        self._events.emit("run:workers", {"n": n})

    def _finished(self, success: bool):
        with self._lock:
            elapsed = time.time() - (self._state["started_at"] or time.time())
            clips = sum(j["clips"] or 0 for j in self._state["jobs"].values())
            self._state.update(running=False, finished={"success": success, "elapsed": elapsed, "clips": clips})
            finished = dict(self._state["finished"])
        self._events.emit("run:finished", finished)
