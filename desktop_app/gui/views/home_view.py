"""
Clip source view (folder/file picker + player names) and run view (pipeline + log).
"""

import os
import cv2

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi"}


def _fmt_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1e9:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f} MB"
    if n >= 1_000:
        return f"{n / 1e3:.1f} KB"
    return f"{n} B"


def _folder_video_size(path: str) -> tuple[int, int]:
    """Return (total_bytes, file_count) for video files in path (non-recursive)."""
    total, count = 0, 0
    try:
        for entry in os.scandir(path):
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in VIDEO_EXTS:
                total += entry.stat().st_size
                count += 1
    except OSError:
        pass
    return total, count


def _folder_video_paths(path: str) -> list[str]:
    """Return sorted list of video file paths in path (non-recursive)."""
    paths = []
    try:
        for entry in os.scandir(path):
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in VIDEO_EXTS:
                paths.append(entry.path)
    except OSError:
        pass
    return sorted(paths)


from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog,
    QRadioButton, QButtonGroup, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QSizePolicy, QScrollArea, QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QImage

from desktop_app.gui.widgets.log_viewer import LogViewer
from desktop_app.gui.widgets.animated_pipeline import AnimatedPipelineWidget
from desktop_app.workers.pipeline_worker import PipelineWorker
from desktop_app.gui.utils.config_manager import ConfigManager

ALL_STAGES = ["ingest", "analyze", "correlate", "clip", "summary"]


class _ThumbnailWorker(QThread):
    """Extract a representative frame from each video in a background thread.

    Emits QImage (not QPixmap) because QPixmap must be created on the GUI thread.
    """
    thumbnail_ready = pyqtSignal(str, QImage)

    def __init__(self, paths: list[str], tw: int, th: int):
        super().__init__()
        self._paths = paths
        self._tw, self._th = tw, th
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for path in self._paths:
            if self._cancelled:
                break
            img = self._grab_frame(path)
            if img is not None:
                self.thumbnail_ready.emit(path, img)

    def _grab_frame(self, path: str) -> "QImage | None":
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return None
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total > 30:
                cap.set(cv2.CAP_PROP_POS_FRAMES, min(total // 10, total - 1))
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            img = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
            return img.scaled(
                self._tw, self._th,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            return None


class _ThumbnailCard(QWidget):
    """Single clip card: thumbnail image + filename."""

    def __init__(self, path: str, tw: int, th: int):
        super().__init__()
        self.setFixedWidth(tw)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._img = QLabel()
        self._img.setFixedSize(tw, th)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setText("…")
        self._img.setStyleSheet(
            "QLabel { background: #0d0f14; border: 1px solid #2a2d35; color: #374151; font-size: 10px; }"
        )
        layout.addWidget(self._img)

        name_lbl = QLabel()
        fm = name_lbl.fontMetrics()
        elided = fm.elidedText(os.path.basename(path), Qt.TextElideMode.ElideRight, tw)
        name_lbl.setText(elided)
        name_lbl.setToolTip(path)
        name_lbl.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(name_lbl)

    def set_thumbnail(self, img: QImage) -> None:
        self._img.setText("")
        self._img.setPixmap(QPixmap.fromImage(img))


class ClipThumbnailGrid(QWidget):
    """Scrollable grid of video clip thumbnails."""

    _COLS = 4
    _TW = 160
    _TH = 90  # 16:9

    def __init__(self):
        super().__init__()
        self._worker: _ThumbnailWorker | None = None
        self._cards: dict[str, _ThumbnailCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: 1px solid #2a2d35; border-radius: 4px; }")

        self._inner = QWidget()
        self._grid_layout = QGridLayout(self._inner)
        self._grid_layout.setSpacing(6)
        self._grid_layout.setContentsMargins(6, 6, 6, 6)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

        self.setVisible(False)

    def load_paths(self, paths: list[str]) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        if not paths:
            self.setVisible(False)
            return

        for i, path in enumerate(paths):
            card = _ThumbnailCard(path, self._TW, self._TH)
            self._grid_layout.addWidget(card, i // self._COLS, i % self._COLS)
            self._cards[path] = card

        self.setVisible(True)

        self._worker = _ThumbnailWorker(paths, self._TW, self._TH)
        self._worker.thumbnail_ready.connect(self._on_thumb)
        self._worker.start()

    def _on_thumb(self, path: str, img: QImage) -> None:
        if path in self._cards:
            self._cards[path].set_thumbnail(img)


class ClipSourceView(QWidget):
    """Clip source selector: folder/file picker and player names."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._build_ui()
        self.reload_config()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(16)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        mode_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._folder_radio = QRadioButton("Folder")
        self._files_radio = QRadioButton("Individual files")
        self._folder_radio.setChecked(True)
        self._mode_group.addButton(self._folder_radio, 0)
        self._mode_group.addButton(self._files_radio, 1)
        mode_row.addWidget(self._folder_radio)
        mode_row.addWidget(self._files_radio)
        mode_row.addStretch()
        root.addLayout(mode_row)

        self._folder_radio.toggled.connect(lambda checked: self._source_stack.setCurrentIndex(0) if checked else None)
        self._files_radio.toggled.connect(lambda checked: self._source_stack.setCurrentIndex(1) if checked else None)

        self._source_stack = QStackedWidget()
        self._source_stack.addWidget(self._build_folder_panel())
        self._source_stack.addWidget(self._build_files_panel())
        root.addWidget(self._source_stack, 1)  # fills available height

        names_row = QHBoxLayout()
        names_lbl = QLabel("Your in-game name(s):")
        names_lbl.setFixedWidth(160)
        names_row.addWidget(names_lbl)
        self._names_edit = QLineEdit()
        self._names_edit.setPlaceholderText("donk666, altName, smurf  (comma-separated)")
        self._names_edit.textChanged.connect(self._on_names_changed)
        names_row.addWidget(self._names_edit)
        root.addLayout(names_row)

    def _build_folder_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select folder containing .mp4 files…")
        self._folder_edit.setReadOnly(True)
        row.addWidget(self._folder_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_folder)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self._folder_size_lbl = QLabel("")
        self._folder_size_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(self._folder_size_lbl)

        self._thumb_grid = ClipThumbnailGrid()
        layout.addWidget(self._thumb_grid, 1)

        return panel

    def _build_files_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Files")
        add_btn.clicked.connect(self._add_files)
        btn_row.addWidget(add_btn)

        clear_btn = QPushButton("Clear all")
        clear_btn.clicked.connect(self._clear_files)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()

        self._files_count_lbl = QLabel("No files selected")
        self._files_count_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        btn_row.addWidget(self._files_count_lbl)

        layout.addLayout(btn_row)

        self._files_list = QListWidget()
        layout.addWidget(self._files_list, 1)
        return panel

    # ------------------------------------------------------------------ public getters (for RunView)

    def get_file_list(self) -> "list[str] | None":
        """Returns list of selected files in files mode, None in folder mode."""
        if self._files_radio.isChecked():
            return [
                self._files_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._files_list.count())
            ]
        return None

    def get_folder(self) -> str:
        return self._folder_edit.text().strip()

    def get_names(self) -> list[str]:
        return [n.strip() for n in self._names_edit.text().split(",") if n.strip()]

    def is_files_mode(self) -> bool:
        return self._files_radio.isChecked()

    # ------------------------------------------------------------------ config

    def reload_config(self):
        config = self.config_manager.load_config()

        folder = config.get("captures_folder", "")
        self._folder_edit.setText(folder)
        if folder and os.path.isdir(folder):
            self._update_folder_info(folder)

        names = config.get("player_names", [])
        if isinstance(names, list):
            self._names_edit.setText(", ".join(names))
        else:
            self._names_edit.setText(str(names))

    def _save_names_to_config(self):
        names = [n.strip() for n in self._names_edit.text().split(",") if n.strip()]
        config = self.config_manager.load_config()
        config["player_names"] = names
        self.config_manager.save_config(config)

    def _save_folder_to_config(self, path: str):
        config = self.config_manager.load_config()
        config["captures_folder"] = path
        self.config_manager.save_config(config)

    # ------------------------------------------------------------------ slots

    def _update_folder_info(self, path: str) -> None:
        size_bytes, count = _folder_video_size(path)
        if count:
            self._folder_size_lbl.setText(
                f"{count} video file{'s' if count != 1 else ''}  ·  {_fmt_size(size_bytes)}"
            )
            self._thumb_grid.load_paths(_folder_video_paths(path))
        else:
            self._folder_size_lbl.setText("No video files found in folder")
            self._thumb_grid.load_paths([])

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select clips folder")
        if path:
            self._folder_edit.setText(path)
            self._save_folder_to_config(path)
            self._update_folder_info(path)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select video files", "", "Video files (*.mp4 *.mkv *.mov *.avi)"
        )
        for path in paths:
            if not self._file_already_in_list(path):
                item = QListWidgetItem(os.path.basename(path))
                item.setData(Qt.ItemDataRole.UserRole, path)
                self._files_list.addItem(item)
        self._update_files_count()

    def _file_already_in_list(self, path: str) -> bool:
        for i in range(self._files_list.count()):
            if self._files_list.item(i).data(Qt.ItemDataRole.UserRole) == path:
                return True
        return False

    def _clear_files(self):
        self._files_list.clear()
        self._update_files_count()

    def _update_files_count(self):
        count = self._files_list.count()
        if count:
            paths = [self._files_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(count)]
            total_bytes = sum(os.path.getsize(p) for p in paths if os.path.exists(p))
            self._files_count_lbl.setText(f"{count} file{'s' if count != 1 else ''} selected  ·  {_fmt_size(total_bytes)}")
        else:
            self._files_count_lbl.setText("No files selected")

    def _on_names_changed(self, _text: str):
        self._save_names_to_config()


class RunView(QWidget):
    """Run controls, pipeline progress, and log."""

    pipeline_finished = pyqtSignal(bool, int)  # success, input_bytes

    def __init__(self, clip_source: ClipSourceView, config_manager: ConfigManager):
        super().__init__()
        self._source = clip_source
        self.config_manager = config_manager
        self._worker = None
        self._input_size_bytes = 0
        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(16)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        run_frame = QFrame()
        run_frame.setStyleSheet("QFrame { background-color: #12151a; border-radius: 6px; border: 1px solid #2a2d35; }")
        run_layout = QVBoxLayout(run_frame)
        run_layout.setContentsMargins(16, 14, 16, 14)
        run_layout.setSpacing(10)

        self._run_btn = QPushButton("FIND HIGHLIGHTS")
        self._run_btn.setObjectName("runButton")
        self._run_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._run_btn.clicked.connect(self._start_pipeline)
        run_layout.addWidget(self._run_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._validation_label = QLabel("")
        self._validation_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self._validation_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        run_layout.addWidget(self._validation_label)

        self._pipeline_widget = AnimatedPipelineWidget()
        self._pipeline_widget.setVisible(False)
        run_layout.addWidget(self._pipeline_widget)

        ctrl_row = QHBoxLayout()
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_pipeline)
        ctrl_row.addWidget(self._pause_btn)
        ctrl_row.addWidget(self._stop_btn)
        self._ctrl_frame = QWidget()
        self._ctrl_frame.setLayout(ctrl_row)
        self._ctrl_frame.setVisible(False)
        run_layout.addWidget(self._ctrl_frame)

        root.addWidget(run_frame)

        self._log_toggle_btn = QPushButton("Show log  ▼")
        self._log_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #6b7280; font-size: 12px; text-align: left; }"
            "QPushButton:hover { color: #c8ccd4; }"
        )
        self._log_toggle_btn.clicked.connect(self._toggle_log)
        root.addWidget(self._log_toggle_btn)

        self._log_viewer = LogViewer()
        self._log_viewer.setVisible(False)
        self._log_viewer.setMinimumHeight(120)
        self._log_viewer.setMaximumHeight(200)
        root.addWidget(self._log_viewer)
        root.addStretch()

    # ------------------------------------------------------------------ run

    def _validate(self) -> str:
        if self._source.is_files_mode():
            if not self._source.get_file_list():
                return "Add at least one video file."
        else:
            if not self._source.get_folder():
                return "Select a folder containing your CS2 clips."
        if not self._source.get_names():
            return "Enter at least one in-game name."
        return ""

    def _start_pipeline(self):
        err = self._validate()
        if err:
            self._validation_label.setText(err)
            return
        self._validation_label.setText("")

        file_list = self._source.get_file_list()

        if file_list:
            self._input_size_bytes = sum(os.path.getsize(p) for p in file_list if os.path.exists(p))
            video_count = len(file_list)
        else:
            folder = self._source.get_folder()
            self._input_size_bytes, video_count = _folder_video_size(folder)

        self._worker = PipelineWorker(stages=ALL_STAGES, file_list=file_list)

        self._pipeline_widget.reset()
        self._pipeline_widget.set_video_count(video_count)

        self._worker.progress_updated.connect(self._on_progress)
        self._worker.stage_started.connect(lambda s: self._log_viewer.add_message(f"Stage: {s}", "info"))
        self._worker.stage_completed.connect(
            lambda s, ok: self._log_viewer.add_message(
                f"{s} done" if ok else f"{s} FAILED", "success" if ok else "error"
            )
        )
        self._worker.job_started.connect(self._pipeline_widget.on_job_started)
        self._worker.job_updated.connect(self._pipeline_widget.on_job_updated)
        self._worker.job_finished.connect(self._pipeline_widget.on_job_finished)
        self._worker.pipeline_count.connect(self._pipeline_widget.on_count_updated)
        self._worker.log_message.connect(lambda m: self._log_viewer.add_message(m, "info"))
        self._worker.error_occurred.connect(lambda e: self._log_viewer.add_message(e, "error"))
        self._worker.finished.connect(self._on_pipeline_done)

        # Seed stepper from config; worker will push the real value once it
        # knows whether GPU is available (workers_count_changed signal).
        _cfg = self.config_manager.load_config()
        _nw  = _cfg.get('pipeline', {}).get('analysis_workers',
                         _cfg.get('analysis_workers', 2))
        self._pipeline_widget.set_worker_target(_nw)
        self._worker.workers_count_changed.connect(self._pipeline_widget.set_worker_target)
        self._pipeline_widget.workers_changed.connect(self._worker.set_target_workers)

        self._set_running(True)
        self._log_viewer.clear_log()
        if not self._log_viewer.isVisible():
            self._toggle_log()
        self._worker.start()

    def _toggle_pause(self):
        if not self._worker:
            return
        if self._worker.is_paused:
            self._worker.resume()
            self._pause_btn.setText("Pause")
        else:
            self._worker.pause()
            self._pause_btn.setText("Resume")

    def _stop_pipeline(self):
        if self._worker:
            self._worker.stop()

    def _on_pipeline_done(self, success: bool):
        self._set_running(False)
        self.pipeline_finished.emit(success, self._input_size_bytes)

    def _set_running(self, running: bool):
        self._run_btn.setVisible(not running)
        self._pipeline_widget.setVisible(running)
        self._ctrl_frame.setVisible(running)
        self._pause_btn.setEnabled(running)
        self._pause_btn.setText("Pause")
        self._stop_btn.setEnabled(running)

    def _on_progress(self, pct: int, msg: str) -> None:
        pass  # AnimatedPipelineWidget handles visual progress; pct unused here

    def _toggle_log(self):
        visible = not self._log_viewer.isVisible()
        self._log_viewer.setVisible(visible)
        self._log_toggle_btn.setText("Hide log  ▲" if visible else "Show log  ▼")
