"""
Qt wrapper around the pipeline: runs PipelineRunner (pipeline.py) on a
QThread and re-emits its channels as Qt signals, so slots run on the GUI
thread.
"""

import sys
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from desktop_app.workers.pipeline import PipelineRunner

_SIGNALS = ('progress_updated', 'stage_started', 'stage_completed', 'log_message', 'error_occurred',
            'finished', 'job_started', 'job_updated', 'job_finished', 'pipeline_count',
            'workers_count_changed')


class PipelineWorker(QThread):

    # ---- signals -------------------------------------------------------
    # Stage-level (kept for log viewer)
    progress_updated = pyqtSignal(int, str)
    stage_started    = pyqtSignal(str)
    stage_completed  = pyqtSignal(str, bool)
    log_message      = pyqtSignal(str)
    error_occurred   = pyqtSignal(str)
    finished         = pyqtSignal(bool)

    # Per-job signals (used by the job-board widget)
    job_started          = pyqtSignal(str, str)   # video_name, stage
    job_updated          = pyqtSignal(str, str)   # video_name, new_stage
    job_finished         = pyqtSignal(str, bool)  # video_name, success
    pipeline_count       = pyqtSignal(int, int)   # videos_done, total
    workers_count_changed = pyqtSignal(int)        # actual n_analyze after GPU check
    # --------------------------------------------------------------------

    def __init__(self, stages: List[str], config_path: str = None, file_list: List[str] = None,
                 requested_workers=None):
        super().__init__()
        self._runner = PipelineRunner(stages, config_path, file_list, requested_workers)
        for name in _SIGNALS:
            getattr(self._runner, name).connect(getattr(self, name).emit)

    @property
    def is_paused(self):
        return self._runner.is_paused

    def run(self):
        self._runner.run()

    def set_target_workers(self, n: int) -> None:
        self._runner.set_target_workers(n)

    def set_gaming_mode(self, on: bool) -> None:
        self._runner.set_gaming_mode(on)

    def pause(self):
        self._runner.pause()

    def resume(self):
        self._runner.resume()

    def stop(self):
        self._runner.stop()

# ---------------------------------------------------------------------------

class CommandLineWorker(QThread):
    """Alternative worker that shells out to the CLI."""

    progress_updated = pyqtSignal(int, str)
    log_message      = pyqtSignal(str)
    error_occurred   = pyqtSignal(str)
    finished         = pyqtSignal(bool)

    def __init__(self, stages: List[str], config_path: str = None):
        super().__init__()
        self.stages = stages
        self.config_path = config_path or str(project_root / "config.yaml")
        self.should_stop = False

    def run(self):
        try:
            self.log_message.emit("Starting pipeline via CLI…")
            stage_arg = "all" if ("all" in self.stages or len(self.stages) == 5) else self.stages[0]
            cmd = [sys.executable, str(project_root / "main.py"), stage_arg]
            self.log_message.emit(f"Running: {' '.join(cmd)}")

            import subprocess
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, universal_newlines=True)
            while True:
                if self.should_stop:
                    proc.terminate()
                    break
                line = proc.stdout.readline()
                if line == '' and proc.poll() is not None:
                    break
                if line:
                    self.log_message.emit(line.strip())

            rc = proc.wait()
            if rc == 0:
                self.progress_updated.emit(100, "Pipeline completed")
                self.finished.emit(True)
            else:
                self.error_occurred.emit(f"Pipeline failed (exit {rc})")
                self.finished.emit(False)
        except Exception as e:
            self.error_occurred.emit(f"CLI execution failed: {e}")
            self.finished.emit(False)

    def stop(self):
        self.should_stop = True
