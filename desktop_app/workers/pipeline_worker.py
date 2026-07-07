"""
Background worker for the CHAOS pipeline.

The core pipeline runs as a true streaming pipeline:
  analyze → correlate → clip
Each video moves to its next stage as soon as it finishes the current one —
no video waits for other videos to finish before advancing.

Fault tolerance: per-video state is persisted in data/video_events/:
  {stem}.json    — analysis events saved after analyze completes
  {stem}.clipped — marker written after all clips for that video are done
On restart, already-clipped videos are counted silently; already-analyzed
videos skip straight to correlate+clip.
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
    job_started          = pyqtSignal(str, str)   # video_name, stage
    job_updated          = pyqtSignal(str, str)   # video_name, new_stage
    job_finished         = pyqtSignal(str, bool)  # video_name, success
    pipeline_count       = pyqtSignal(int, int)   # videos_done, total
    workers_count_changed = pyqtSignal(int)        # actual n_analyze after GPU check
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
        self._target_workers: int = 4  # adjusted at runtime via set_target_workers

    # ------------------------------------------------------------------ run

    def run(self):
        try:
            self.log_message.emit("Starting CHAOS pipeline…")
            config = self.config_manager.load_config()
            if not config:
                self.error_occurred.emit("Failed to load configuration")
                self.finished.emit(False)
                return

            # Normalize relative paths against project root so .clipped / .json
            # cache files are written to (and read from) the same absolute location
            # regardless of the CWD when the app is launched.
            for _k in ('data_folder', 'final_clips_folder'):
                if _k in config and not os.path.isabs(config[_k]):
                    config[_k] = str((project_root / config[_k]).resolve())

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

        Fault tolerance: on restart, videos with cached events skip analysis;
        videos with a .clipped marker are counted immediately and skipped.
        """
        try:
            import torch
            use_gpu = torch.cuda.is_available()
            if use_gpu:
                self.log_message.emit(f"GPU: {torch.cuda.get_device_name(0)}")
        except ImportError:
            use_gpu = False

        _pipe = config.get('pipeline', {})
        n_analyze = (
            1 if use_gpu
            else max(1, _pipe.get('analysis_workers',
                                  config.get('analysis_workers', min(4, os.cpu_count() or 1))))
        )
        n_clip = max(1, _pipe.get('clip_workers',
                                  config.get('clip_workers', min(4, os.cpu_count() or 1))))

        mode = "GPU (single worker)" if use_gpu else f"{n_analyze} CPU workers"
        self.log_message.emit(f"Analyze: {mode}  |  Clip: {n_clip} workers")

        ffmpeg = clipper._get_ffmpeg()
        out_folder = config['final_clips_folder']

        video_events_dir = os.path.join(config['data_folder'], 'video_events')
        os.makedirs(video_events_dir, exist_ok=True)

        all_events: list = []
        all_highlights: list = []
        clip_futures: list = []
        pending_clips: dict = defaultdict(int)
        clip_counter = [0]
        clip_lock = Lock()
        completed = [0]
        n_total = len(video_paths)

        self.stage_started.emit("analyze")

        # Partition by existing state
        pre_clipped: list = []
        pre_analyzed: dict = {}   # path → events
        needs_analysis: list = []

        for path in video_paths:
            stem = os.path.splitext(os.path.basename(path))[0]
            events_file  = os.path.join(video_events_dir, f"{stem}.json")
            clipped_file = os.path.join(video_events_dir, f"{stem}.clipped")
            if os.path.exists(clipped_file) and os.path.exists(events_file):
                pre_clipped.append(path)
            elif os.path.exists(events_file):
                try:
                    with open(events_file) as f:
                        pre_analyzed[path] = json.load(f)
                except Exception:
                    needs_analysis.append(path)
            else:
                needs_analysis.append(path)

        if pre_clipped:
            self.log_message.emit(f"Skipping {len(pre_clipped)} already-finished videos")
        if pre_analyzed:
            self.log_message.emit(f"Resuming: {len(pre_analyzed)} videos skip analysis")
        if needs_analysis:
            self.log_message.emit(f"Analyzing: {len(needs_analysis)} videos")

        # Pre-populate the job board with the full queue so users can see all videos
        for path in list(pre_analyzed.keys()) + needs_analysis:
            self.job_started.emit(os.path.basename(path), 'queued')

        with ThreadPoolExecutor(max_workers=n_clip) as clip_pool:

            # Already-clipped videos: count silently, no UI card
            if pre_clipped:
                with clip_lock:
                    completed[0] += len(pre_clipped)
                self.pipeline_count.emit(completed[0], n_total)

            # Pre-analyzed: cached events, go straight to correlate+clip
            for path, events in pre_analyzed.items():
                if self.should_stop:
                    break
                name = os.path.basename(path)
                self.job_started.emit(name, 'correlate')
                all_events.extend(events)
                self._after_analyze(
                    path, name, events, config,
                    all_highlights,
                    clip_pool, clip_futures, clip_counter, clip_lock,
                    pending_clips, completed, n_total, ffmpeg, out_folder,
                    video_events_dir,
                )

            if not self.should_stop and needs_analysis:
                if n_analyze == 1:
                    self._load_inline_models(config, use_gpu)
                    for path in needs_analysis:
                        if self.should_stop:
                            break
                        self._handle_video(
                            path, config, use_gpu,
                            all_events, all_highlights,
                            clip_pool, clip_futures, clip_counter, clip_lock,
                            pending_clips, completed, n_total, ffmpeg, out_folder,
                            video_events_dir,
                        )
                else:
                    # Pool ceiling: workers beyond n_analyze are idle until user
                    # increments the stepper, then tasks start immediately.
                    _pool_cap = min(os.cpu_count() or 4, 8)
                    with ProcessPoolExecutor(
                        max_workers=_pool_cap,
                        initializer=analyzers._init_analysis_worker,
                        initargs=(config['whisper_model'],),
                    ) as analyze_pool:

                        pending_queue = list(needs_analysis)
                        in_flight: dict = {}

                        def _submit_next():
                            if pending_queue and not self.should_stop:
                                path = pending_queue.pop(0)
                                name = os.path.basename(path)
                                self.job_started.emit(name, 'analyze')
                                f = analyze_pool.submit(analyzers._analyze_video_worker, path, config)
                                in_flight[f] = path

                        self._target_workers = n_analyze
                        self.workers_count_changed.emit(n_analyze)

                        def _maybe_submit():
                            while (len(in_flight) < self._target_workers
                                   and pending_queue
                                   and not self.should_stop):
                                _submit_next()

                        _maybe_submit()

                        while in_flight:
                            # Short timeout so a + press takes effect in ≤100 ms
                            done_set, _ = wait(set(in_flight), return_when=FIRST_COMPLETED,
                                               timeout=0.1)
                            _maybe_submit()  # picks up any target increase immediately
                            for future in done_set:
                                path = in_flight.pop(future)
                                name = os.path.basename(path)
                                try:
                                    events = future.result()
                                except Exception as e:
                                    self.log_message.emit(f"Analyze failed {name}: {e}")
                                    self.job_finished.emit(name, False)
                                    _maybe_submit()
                                    continue

                                all_events.extend(events)
                                self._after_analyze(
                                    path, name, events, config,
                                    all_highlights,
                                    clip_pool, clip_futures, clip_counter, clip_lock,
                                    pending_clips, completed, n_total, ffmpeg, out_folder,
                                    video_events_dir,
                                )
                                _maybe_submit()

            # Wait for all clip futures — callbacks handle job_finished/pipeline_count
            if clip_futures:
                wait([f for f, _ in clip_futures])

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
                      pending_clips, completed, n_total, ffmpeg, out_folder,
                      video_events_dir=None):
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

        all_events.extend(events)
        self._after_analyze(
            path, name, events, config,
            all_highlights,
            clip_pool, clip_futures, clip_counter, clip_lock,
            pending_clips, completed, n_total, ffmpeg, out_folder,
            video_events_dir,
        )

    def _after_analyze(self, path, name, events, config,
                       all_highlights,
                       clip_pool, clip_futures, clip_counter, clip_lock,
                       pending_clips, completed, n_total, ffmpeg, out_folder,
                       video_events_dir=None):
        """Persist events, correlate, and submit clips immediately after analysis."""
        stem = os.path.splitext(name)[0]

        # Persist events so we can resume if interrupted
        if video_events_dir:
            try:
                with open(os.path.join(video_events_dir, f"{stem}.json"), 'w') as f:
                    json.dump(events, f)
            except Exception:
                pass

        self.job_updated.emit(name, 'correlate')
        highlights = correlator.correlate_video_events(path, events, config)
        all_highlights.extend(highlights)
        self.log_message.emit(f"{name}: {len(highlights)} clip(s) found")

        if not highlights:
            with clip_lock:
                completed[0] += 1
                cnt = completed[0]
            # No clips to make — mark as fully done
            if video_events_dir:
                try:
                    open(os.path.join(video_events_dir, f"{stem}.clipped"), 'w').close()
                except Exception:
                    pass
            self.job_finished.emit(name, True)
            self.pipeline_count.emit(cnt, n_total)
            return

        self.job_updated.emit(name, 'clip')
        pending_clips[name] = len(highlights)
        for h in highlights:
            with clip_lock:
                idx = clip_counter[0]
                clip_counter[0] += 1
            f = clip_pool.submit(clipper._clip_one, idx, h, out_folder, ffmpeg)
            f.add_done_callback(
                self._make_clip_callback(name, stem, video_events_dir, pending_clips, completed, clip_lock, n_total)
            )
            clip_futures.append((f, name))

    def _make_clip_callback(self, name, stem, video_events_dir, pending_clips, completed, clip_lock, n_total):
        def _callback(future):
            try:
                future.result()
            except Exception as e:
                self.log_message.emit(f"Clip error ({name}): {e}")
            emit_done = False
            emit_cnt = 0
            with clip_lock:
                pending_clips[name] -= 1
                if pending_clips[name] == 0:
                    completed[0] += 1
                    emit_done = True
                    emit_cnt = completed[0]
                    if video_events_dir:
                        try:
                            open(os.path.join(video_events_dir, f"{stem}.clipped"), 'w').close()
                        except Exception:
                            pass
            if emit_done:
                self.job_finished.emit(name, True)
                self.pipeline_count.emit(emit_cnt, n_total)
        return _callback

    # ------------------------------------------------------------------ control

    def set_target_workers(self, n: int) -> None:
        """Adjust analysis concurrency live. Excess in-flight jobs finish naturally."""
        self._target_workers = max(1, n)
        self.log_message.emit(f"Analysis workers → {self._target_workers}")

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
