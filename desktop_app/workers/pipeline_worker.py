"""
Background worker for the CHAOS pipeline.

The core pipeline runs as a true streaming pipeline:
  analyze → correlate → clip
Each video moves to its next stage as soon as it finishes the current one —
no video waits for other videos to finish before advancing.
"""

import sys
import os
import json
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from pathlib import Path
from threading import Lock
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chaos_lib import ingestion, analyzers, correlator, clipper, summary
from desktop_app.gui.utils.config_manager import ConfigManager


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
    job_started    = pyqtSignal(str, str)   # video_name, stage
    job_updated    = pyqtSignal(str, str)   # video_name, new_stage
    job_finished   = pyqtSignal(str, bool)  # video_name, success
    pipeline_count = pyqtSignal(int, int)   # videos_done, total
    # --------------------------------------------------------------------

    def __init__(self, stages: List[str], config_path: str = None, file_list: List[str] = None):
        super().__init__()
        self.stages = stages
        self.config_path = config_path or str(project_root / "config.yaml")
        self.config_manager = ConfigManager(self.config_path)
        self.file_list = file_list
        self.is_paused = False
        self.should_stop = False
        self._ocr = None
        self._whisper_model = None

    # ------------------------------------------------------------------ run

    def run(self):
        try:
            self.log_message.emit("Starting CHAOS pipeline…")
            config = self.config_manager.load_config()
            if not config:
                self.error_occurred.emit("Failed to load configuration")
                self.finished.emit(False)
                return

            errors = self.config_manager.validate_config(
                config, skip_folder_check=self.file_list is not None
            )
            if errors:
                self.error_occurred.emit(f"Config errors: {'; '.join(errors)}")
                self.finished.emit(False)
                return

            os.makedirs(config['data_folder'],       exist_ok=True)
            os.makedirs(config['final_clips_folder'], exist_ok=True)

            # ---- Ingest ----
            self.stage_started.emit("ingest")
            self.log_message.emit("Creating video manifest…")
            ingestion.create_manifest(config, file_list=self.file_list)
            self.log_message.emit("Video manifest created")
            self.stage_completed.emit("ingest", True)

            if self.should_stop:
                self.finished.emit(False)
                return

            manifest_path = os.path.join(config['data_folder'], 'manifest.json')
            with open(manifest_path) as f:
                video_paths = json.load(f)

            if not video_paths:
                self.log_message.emit("No videos to process.")
                self.finished.emit(True)
                return

            self.pipeline_count.emit(0, len(video_paths))

            # ---- Streaming analyze → correlate → clip ----
            all_events, all_highlights = self._run_streaming(video_paths, config)

            if self.should_stop:
                self.finished.emit(False)
                return

            # Write consolidated JSON for debug / downstream tools
            with open(os.path.join(config['data_folder'], 'all_events.json'), 'w') as f:
                json.dump(all_events, f, indent=2)

            all_highlights.sort(key=lambda x: x['score'], reverse=True)
            with open(os.path.join(config['data_folder'], 'ordered_highlights.json'), 'w') as f:
                json.dump(all_highlights, f, indent=2)

            # ---- Summary ----
            self.stage_started.emit("summary")
            self.log_message.emit("Generating summary…")
            summary.generate_summary(config)
            self.log_message.emit("Summary generated")
            self.stage_completed.emit("summary", True)

            self.progress_updated.emit(100, "Pipeline complete!")
            self.finished.emit(True)

        except Exception as e:
            self.error_occurred.emit(f"Pipeline failed: {str(e)}")
            self.finished.emit(False)

    # ------------------------------------------------------------------ streaming core

    def _run_streaming(self, video_paths: list, config: dict) -> tuple:
        """
        Each video streams analyze → correlate → clip without waiting for
        other videos.  Returns (all_events, all_highlights).
        """
        try:
            import torch
            use_gpu = torch.cuda.is_available()
            if use_gpu:
                self.log_message.emit(f"GPU: {torch.cuda.get_device_name(0)}")
        except ImportError:
            use_gpu = False

        n_analyze = (
            1 if use_gpu
            else max(1, config.get('analysis_workers', min(4, os.cpu_count() or 1)))
        )
        n_clip = max(1, config.get('clip_workers', min(4, os.cpu_count() or 1)))

        mode = "GPU (single worker)" if use_gpu else f"{n_analyze} CPU workers"
        self.log_message.emit(f"Analyze: {mode}  |  Clip: {n_clip} workers")

        ffmpeg = clipper._get_ffmpeg()
        out_folder = config['final_clips_folder']

        all_events: list = []
        all_highlights: list = []
        clip_futures: list = []          # (future, video_name)
        pending_clips: dict = defaultdict(int)  # video_name → remaining clips
        clip_counter = [0]
        clip_lock = Lock()
        completed = [0]
        n_total = len(video_paths)

        self.stage_started.emit("analyze")

        with ThreadPoolExecutor(max_workers=n_clip) as clip_pool:

            if n_analyze == 1:
                self._load_inline_models(config, use_gpu)
                for path in video_paths:
                    if self.should_stop:
                        break
                    self._handle_video(
                        path, config, use_gpu,
                        all_events, all_highlights,
                        clip_pool, clip_futures, clip_counter, clip_lock,
                        pending_clips, completed, n_total, ffmpeg, out_folder,
                    )
            else:
                with ProcessPoolExecutor(
                    max_workers=n_analyze,
                    initializer=analyzers._init_analysis_worker,
                    initargs=(config['whisper_model'],),
                ) as analyze_pool:

                    # Submit n_analyze videos initially, then refill as slots free
                    pending_queue = list(video_paths)
                    in_flight: dict = {}

                    def _submit_next():
                        if pending_queue and not self.should_stop:
                            path = pending_queue.pop(0)
                            name = os.path.basename(path)
                            self.job_started.emit(name, 'analyze')
                            f = analyze_pool.submit(analyzers._analyze_video_worker, path, config)
                            in_flight[f] = path

                    for _ in range(min(n_analyze, len(pending_queue))):
                        _submit_next()

                    while in_flight:
                        done_set, _ = wait(set(in_flight), return_when=FIRST_COMPLETED)
                        for future in done_set:
                            path = in_flight.pop(future)
                            name = os.path.basename(path)
                            try:
                                events = future.result()
                            except Exception as e:
                                self.log_message.emit(f"Analyze failed {name}: {e}")
                                self.job_finished.emit(name, False)
                                _submit_next()
                                continue

                            self._after_analyze(
                                path, name, events, config,
                                all_events, all_highlights,
                                clip_pool, clip_futures, clip_counter, clip_lock,
                                pending_clips, completed, n_total, ffmpeg, out_folder,
                            )
                            _submit_next()

            # Wait for all clip jobs, emitting finished once a video's clips are done
            future_to_name = {f: name for f, name in clip_futures}
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    future.result()
                except Exception as e:
                    self.log_message.emit(f"Clip error ({name}): {e}")
                pending_clips[name] -= 1
                if pending_clips[name] == 0:
                    completed[0] += 1
                    self.job_finished.emit(name, True)
                    self.pipeline_count.emit(completed[0], n_total)

        # Emit stage markers so the log viewer still sees them
        self.stage_completed.emit("analyze", True)
        self.stage_started.emit("correlate")
        self.stage_completed.emit("correlate", True)
        self.stage_started.emit("clip")
        self.stage_completed.emit("clip", True)

        return all_events, all_highlights

    # ------------------------------------------------------------------ helpers

    def _load_inline_models(self, config: dict, use_gpu: bool) -> None:
        """Load OCR + Whisper into this thread (GPU / single-worker path)."""
        import easyocr
        import platform
        import whisper as _whisper
        self.log_message.emit("Loading AI models…")
        if platform.system() == 'Darwin' and use_gpu:
            self._ocr = easyocr.Reader(['en'], gpu=False)
        else:
            self._ocr = easyocr.Reader(['en'], gpu=use_gpu)
        device = 'cuda' if use_gpu else 'cpu'
        self._whisper_model = _whisper.load_model(config['whisper_model'], device=device)
        self.log_message.emit("AI models ready")

    def _handle_video(self, path, config, use_gpu,
                      all_events, all_highlights,
                      clip_pool, clip_futures, clip_counter, clip_lock,
                      pending_clips, completed, n_total, ffmpeg, out_folder):
        """Sequential path: analyze inline then hand off."""
        name = os.path.basename(path)
        self.job_started.emit(name, 'analyze')
        try:
            temp_dir = os.path.join(config['data_folder'], 'temp_audio')
            kills = analyzers.analyze_killfeed(path, config, self._ocr)
            voice, spikes = analyzers.analyze_audio(path, self._whisper_model, temp_dir)
            events = kills + spikes + voice
        except Exception as e:
            self.log_message.emit(f"Analyze failed {name}: {e}")
            self.job_finished.emit(name, False)
            return

        self._after_analyze(
            path, name, events, config,
            all_events, all_highlights,
            clip_pool, clip_futures, clip_counter, clip_lock,
            pending_clips, completed, n_total, ffmpeg, out_folder,
        )

    def _after_analyze(self, path, name, events, config,
                       all_events, all_highlights,
                       clip_pool, clip_futures, clip_counter, clip_lock,
                       pending_clips, completed, n_total, ffmpeg, out_folder):
        """Correlate + submit clips immediately after a video finishes analysis."""
        all_events.extend(events)

        self.job_updated.emit(name, 'correlate')
        highlights = correlator.correlate_video_events(path, events, config)
        all_highlights.extend(highlights)
        self.log_message.emit(f"{name}: {len(highlights)} clip(s) found")

        if not highlights:
            completed[0] += 1
            self.job_finished.emit(name, True)
            self.pipeline_count.emit(completed[0], n_total)
            return

        self.job_updated.emit(name, 'clip')
        pending_clips[name] = len(highlights)
        for h in highlights:
            with clip_lock:
                idx = clip_counter[0]
                clip_counter[0] += 1
            f = clip_pool.submit(clipper._clip_one, idx, h, out_folder, ffmpeg)
            clip_futures.append((f, name))

    # ------------------------------------------------------------------ control

    def pause(self):
        self.is_paused = True
        self.log_message.emit("Pipeline paused")

    def resume(self):
        self.is_paused = False
        self.log_message.emit("Pipeline resumed")

    def stop(self):
        self.should_stop = True
        self.log_message.emit("Stopping pipeline…")


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
