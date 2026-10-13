"""
Background worker for the CHAOS pipeline.

The core pipeline runs as a true streaming pipeline:
  analyze → correlate → clip
Each video moves to its next stage as soon as it finishes the current one —
no video waits for other videos to finish before advancing.

Fault tolerance: per-video state is persisted in data/video_events/:
  {stem}.json    — analysis events saved after analyze completes
  {stem}.clipped — written after all clips for that video are done; records
                   the video's highlights and the clip file each was cut to
On restart, a clipped video only counts as finished while its clip files are
still in the output folder; if any were deleted, it re-correlates from cached
events and recuts just the missing ones. Already-analyzed videos skip straight
to correlate+clip. Cached events whose audio analysis is out of date (older
version, or missing what voice-chat moments or subtitles need) get only their
audio redone; their kills are kept.
"""

import sys
import os
import re
import glob
import json
import multiprocessing
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from threading import Lock
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chaos_lib import ingestion, analyzers, correlator, clipper, summary, subtitles
from chaos_lib.resources import plan_analysis_workers
from desktop_app.gui.utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# .clipped markers

def _read_clip_record(marker: str) -> list | None:
    """Highlights recorded in a .clipped marker, or None for an unreadable
    or legacy (empty) marker that doesn't say which clips were cut."""
    try:
        with open(marker) as f:
            return json.load(f)['highlights']
    except Exception:
        return None


def _write_clip_record(marker: str, highlights: list) -> None:
    try:
        with open(marker, 'w') as f:
            json.dump({'highlights': highlights}, f)
    except Exception:
        pass


def _clip_exists(out_folder: str, h: dict) -> bool:
    name = h.get('clip_filename')
    if not name:
        return False
    path = os.path.join(out_folder, name)
    return os.path.exists(path) and os.path.getsize(path) > 0


def _clips_present(record: list | None, out_folder: str, stem: str) -> bool:
    """Whether a finished video's clips are still in the output folder."""
    if record is not None:
        return all(_clip_exists(out_folder, h) for h in record)
    # Legacy marker: no filenames, so settle for any clip of this video.
    pattern = f"*_{glob.escape(stem[:20])}*.mp4"
    return bool(glob.glob(os.path.join(out_folder, pattern))
                or glob.glob(os.path.join(out_folder, 'conversations', pattern)))


def _clip_key(h: dict) -> tuple:
    return (h.get('kind'), round(h['clip_start'], 2), round(h['clip_end'], 2))


def _next_clip_index(out_folder: str) -> int:
    """Highest numeric prefix among existing clips, so new clips never reuse
    (and get mistaken for) the name of a clip from an earlier run."""
    highest = 0
    try:
        for name in os.listdir(out_folder):
            m = re.match(r'(\d+)_', name)
            if m:
                highest = max(highest, int(m.group(1)))
    except OSError:
        pass
    return highest


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
        self.stages = stages
        self.config_path = config_path or str(project_root / "config.yaml")
        self.config_manager = ConfigManager(self.config_path)
        self.file_list = file_list
        self.requested_workers = requested_workers  # None → from config ("auto" = as many as fit)
        self.is_paused = False
        self.should_stop = False
        self._target_workers: int = 1  # adjusted at runtime via set_target_workers
        self._max_workers: int = 1     # pool size from the resource plan
        # Shared with every analysis process: set while the user is playing.
        self._gaming_event = multiprocessing.get_context('spawn').Event()
        self._workers_before_gaming: int | None = None

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
        _pipe = config.get('pipeline', {})
        requested = self.requested_workers
        if requested is None:
            requested = _pipe.get('analysis_workers', config.get('analysis_workers'))
        # Each analysis worker is its own process with its own OCR + Whisper
        # models; the plan sizes the pool from the models' measured memory cost
        # and this machine's free VRAM (or RAM/cores without CUDA).
        plan = plan_analysis_workers(config, requested, n_videos=len(video_paths))
        self._max_workers = plan.max_workers
        n_analyze = plan.workers
        if self._gaming_event.is_set():
            self._workers_before_gaming = n_analyze
            n_analyze = 1
        n_clip = max(1, _pipe.get('clip_workers',
                                  config.get('clip_workers', min(4, os.cpu_count() or 1))))

        self.log_message.emit(plan.summary)
        self.log_message.emit(f"Clip: {n_clip} workers")

        ffmpeg = clipper._get_ffmpeg()
        out_folder = config['final_clips_folder']
        subs = subtitles.options(config)

        video_events_dir = os.path.join(config['data_folder'], 'video_events')
        os.makedirs(video_events_dir, exist_ok=True)

        all_events: list = []
        all_highlights: list = []
        clip_futures: list = []
        pending_clips: dict = defaultdict(int)
        clip_counter = [_next_clip_index(out_folder)]
        clip_lock = Lock()
        completed = [0]
        n_total = len(video_paths)

        self.stage_started.emit("analyze")

        # Partition by existing state
        pre_clipped: list = []
        pre_analyzed: dict = {}   # path → events
        needs_analysis: list = []
        stale_audio: dict = {}    # path → cached events whose audio analysis gets redone
        moments_only: set = set() # already clipped: only cut the new voice-chat clips
        prior_clips: dict = {}    # path → highlights a previous run cut (some since deleted)
        recut: int = 0
        redo_kills: int = 0

        def _load_events(events_file):
            try:
                with open(events_file) as f:
                    return json.load(f)
            except Exception:
                return None

        for path in video_paths:
            stem = os.path.splitext(os.path.basename(path))[0]
            events_file  = os.path.join(video_events_dir, f"{stem}.json")
            clipped_file = os.path.join(video_events_dir, f"{stem}.clipped")
            events = _load_events(events_file) if os.path.exists(events_file) else None
            if events is None:
                needs_analysis.append(path)
            elif analyzers.kills_are_stale(events):
                # Kill detection has improved since: analyse again. Clips
                # whose window comes out the same keep their file.
                if os.path.exists(clipped_file):
                    prior_clips[path] = _read_clip_record(clipped_file) or []
                    os.remove(clipped_file)
                needs_analysis.append(path)
                redo_kills += 1
            elif os.path.exists(clipped_file):
                # Finished before voice-chat moments existed: find those, but
                # leave its kill clips alone (turning subtitles on later
                # doesn't recut finished videos either).
                if analyzers.audio_is_stale(events, config, check_captions=False):
                    stale_audio[path] = events
                    moments_only.add(path)
                    os.remove(clipped_file)
                else:
                    record = _read_clip_record(clipped_file)
                    if _clips_present(record, out_folder, stem):
                        pre_clipped.append(path)
                        all_highlights.extend(record or [])
                    else:
                        # Clips were deleted from the output folder: recut
                        # them from the cached events.
                        os.remove(clipped_file)
                        prior_clips[path] = record or []
                        pre_analyzed[path] = events
                        recut += 1
            elif analyzers.audio_is_stale(events, config):
                stale_audio[path] = events
            else:
                pre_analyzed[path] = events

        if pre_clipped:
            self.log_message.emit(f"Skipping {len(pre_clipped)} already-finished videos")
        if recut:
            self.log_message.emit(f"Recutting clips missing from the output folder: {recut} videos")
        if redo_kills:
            self.log_message.emit(f"Re-reading kills with improved detection: {redo_kills} videos")
        if pre_analyzed:
            self.log_message.emit(f"Resuming: {len(pre_analyzed)} videos skip analysis")
        if stale_audio:
            self.log_message.emit(f"Updating voice-chat analysis: {len(stale_audio)} videos (kills kept)")
        if needs_analysis:
            self.log_message.emit(f"Analyzing: {len(needs_analysis)} videos")
        needs_analysis += list(stale_audio)

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
                    video_events_dir, subs, prior=prior_clips.get(path),
                )

            if not self.should_stop and needs_analysis:
                # The pool holds up to plan.max_workers processes, spawned on
                # demand: only _target_workers videos are in flight, and the
                # stepper can raise that live up to what fits in memory.
                analyze_pool_cm = analyzers.make_analysis_pool(
                    config, plan, self._gaming_event, self._download_progress())

                def submit_task(path):
                    if path in stale_audio:
                        return analyze_pool_cm.submit(
                            analyzers._reanalyze_audio_worker, path, config, stale_audio[path])
                    return analyze_pool_cm.submit(analyzers._analyze_video_worker, path, config)

                with analyze_pool_cm:

                    pending_queue = list(needs_analysis)
                    in_flight: dict = {}

                    def _submit_next():
                        if pending_queue and not self.should_stop:
                            path = pending_queue.pop(0)
                            name = os.path.basename(path)
                            self.job_started.emit(name, 'analyze')
                            f = submit_task(path)
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
                                video_events_dir, subs, moments_only=path in moments_only,
                                prior=prior_clips.get(path),
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

    def _download_progress(self):
        """Log the one-time laughter model download every 10%."""
        last = [-1]

        def progress(done, total):
            pct = int(done * 100 / total) // 10 * 10 if total else 0
            if pct != last[0]:
                last[0] = pct
                self.log_message.emit(f"Downloading laughter model (one time, ~360 MB): {pct}%")
        return progress

    def _after_analyze(self, path, name, events, config,
                       all_highlights,
                       clip_pool, clip_futures, clip_counter, clip_lock,
                       pending_clips, completed, n_total, ffmpeg, out_folder,
                       video_events_dir=None, subs=None, moments_only=False, prior=None):
        """Persist events, correlate, and submit clips immediately after analysis.
        `moments_only` cuts just the voice-chat clips (for a video whose kill
        clips were made by an earlier run). `prior` holds the highlights an
        earlier run cut for this video: those whose file still exists keep it
        and only the rest are cut."""
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
        if moments_only:
            highlights = [h for h in highlights if h.get('kind') in ('funny', 'conversation')]
        all_highlights.extend(highlights)
        self.log_message.emit(f"{name}: {len(highlights)} clip(s) found")

        existing = {_clip_key(h): h['clip_filename'] for h in prior or []
                    if _clip_exists(out_folder, h)}
        to_cut = []
        for h in highlights:
            if _clip_key(h) in existing:
                h['clip_filename'] = existing[_clip_key(h)]
            else:
                to_cut.append(h)

        if not to_cut:
            with clip_lock:
                completed[0] += 1
                cnt = completed[0]
            # No clips to make — mark as fully done
            if video_events_dir:
                _write_clip_record(os.path.join(video_events_dir, f"{stem}.clipped"), highlights)
            self.job_finished.emit(name, True)
            self.pipeline_count.emit(cnt, n_total)
            return

        self.job_updated.emit(name, 'clip')
        pending_clips[name] = len(to_cut)
        for h in to_cut:
            with clip_lock:
                idx = clip_counter[0]
                clip_counter[0] += 1
            f = clip_pool.submit(clipper._clip_one, idx, h, out_folder, ffmpeg, subs)
            f.add_done_callback(
                self._make_clip_callback(name, stem, highlights, video_events_dir,
                                         pending_clips, completed, clip_lock, n_total)
            )
            clip_futures.append((f, name))

    def _make_clip_callback(self, name, stem, highlights, video_events_dir,
                            pending_clips, completed, clip_lock, n_total):
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
                        _write_clip_record(os.path.join(video_events_dir, f"{stem}.clipped"),
                                           highlights)
            if emit_done:
                self.job_finished.emit(name, True)
                self.pipeline_count.emit(emit_cnt, n_total)
        return _callback

    # ------------------------------------------------------------------ control

    def set_target_workers(self, n: int) -> None:
        """Adjust analysis concurrency live, up to what the resource plan says
        fits. Excess in-flight jobs finish naturally."""
        clamped = max(1, min(n, self._max_workers))
        if self._gaming_event.is_set():
            # Remember the choice for when gaming mode ends; stay at one meanwhile.
            self._workers_before_gaming = clamped
            clamped = 1
        self._target_workers = clamped
        if clamped != n:
            self.workers_count_changed.emit(clamped)
        self.log_message.emit(f"Analysis workers → {self._target_workers}")

    def set_gaming_mode(self, on: bool) -> None:
        """Throttle while the user plays: one analysis worker, idle CPU
        priority, and each worker sleeps ~3x as long as it works so the GPU
        and CPU stay mostly free for the game. In-flight work continues,
        throttled, rather than being cancelled."""
        if on == self._gaming_event.is_set():
            return
        if on:
            self._workers_before_gaming = self._target_workers
            self._gaming_event.set()
            self._target_workers = 1
            self.log_message.emit("Gaming mode on: analysis throttled to 1 worker at low priority")
        else:
            self._gaming_event.clear()
            self._target_workers = max(1, min(self._workers_before_gaming or 1, self._max_workers))
            self.log_message.emit(f"Gaming mode off: back to {self._target_workers} workers")
        self.workers_count_changed.emit(self._target_workers)

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
