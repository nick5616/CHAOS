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
    QLineEdit, QFileDialog, QApplication, QDialog, QTextEdit,
    QRadioButton, QButtonGroup, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QSizePolicy, QScrollArea, QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QPixmap, QImage

from desktop_app.gui.widgets.log_viewer import LogViewer
from desktop_app.gui.widgets.animated_pipeline import AnimatedPipelineWidget
from desktop_app.workers.pipeline_worker import PipelineWorker
from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.utils.system_detector import SystemDetector

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


class _ThumbnailCard(QFrame):
    """Single clip card: thumbnail image + filename. Click to toggle selection."""

    toggled = pyqtSignal(str, bool)  # path, selected

    def __init__(self, path: str, tw: int, th: int):
        super().__init__()
        self._path = path
        self._selected = True
        self.setObjectName("thumbCard")
        self.setFixedWidth(tw + 8)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self._img = QLabel()
        self._img.setFixedSize(tw, th)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setText("…")
        self._img.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._img.setStyleSheet(
            "QLabel { background: #0d0f14; border: 1px solid #2a2d35; color: #374151; font-size: 10px; }"
        )
        layout.addWidget(self._img)

        name_lbl = QLabel()
        fm = name_lbl.fontMetrics()
        elided = fm.elidedText(os.path.basename(path), Qt.TextElideMode.ElideRight, tw)
        name_lbl.setText(elided)
        name_lbl.setToolTip(path)
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name_lbl.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(name_lbl)

        self._apply_border()

    def set_thumbnail(self, img: QImage) -> None:
        self._img.setText("")
        self._img.setPixmap(QPixmap.fromImage(img))

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool, emit: bool = True) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_border()
        if emit:
            self.toggled.emit(self._path, self._selected)

    def _apply_border(self) -> None:
        color = "#e8963c" if self._selected else "transparent"
        self.setStyleSheet(f"#thumbCard {{ border: 2px solid {color}; border-radius: 4px; }}")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_selected(not self._selected)
        super().mousePressEvent(event)


class ClipThumbnailGrid(QWidget):
    """Scrollable grid of video clip thumbnails. Clips start selected; click to deselect."""

    selection_changed = pyqtSignal()

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
            card.toggled.connect(self._on_card_toggled)
            self._grid_layout.addWidget(card, i // self._COLS, i % self._COLS)
            self._cards[path] = card

        self.setVisible(True)

        self._worker = _ThumbnailWorker(paths, self._TW, self._TH)
        self._worker.thumbnail_ready.connect(self._on_thumb)
        self._worker.start()

    def _on_thumb(self, path: str, img: QImage) -> None:
        if path in self._cards:
            self._cards[path].set_thumbnail(img)

    def _on_card_toggled(self, _path: str, _selected: bool) -> None:
        self.selection_changed.emit()

    def get_all_paths(self) -> list[str]:
        return list(self._cards.keys())

    def get_selected_paths(self) -> list[str]:
        return [path for path, card in self._cards.items() if card.is_selected()]

    def has_clips(self) -> bool:
        return bool(self._cards)


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
        self._thumb_grid.selection_changed.connect(self._on_clip_selection_changed)
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
        """Returns the explicit list of files to process: the added files in files
        mode, or the checked (non-deselected) clips in folder mode. None only when
        no folder has been loaded yet."""
        if self._files_radio.isChecked():
            return [
                self._files_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._files_list.count())
            ]
        if self._thumb_grid.has_clips():
            return self._thumb_grid.get_selected_paths()
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

    def _on_clip_selection_changed(self) -> None:
        selected = self._thumb_grid.get_selected_paths()
        total = self._thumb_grid.get_all_paths()
        size_bytes = sum(os.path.getsize(p) for p in selected if os.path.exists(p))
        if len(selected) == len(total):
            self._folder_size_lbl.setText(
                f"{len(total)} video file{'s' if len(total) != 1 else ''}  ·  {_fmt_size(size_bytes)}"
            )
        else:
            self._folder_size_lbl.setText(
                f"{len(selected)} of {len(total)} clips selected  ·  {_fmt_size(size_bytes)}"
            )

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


class _CudaInstallWorker(QThread):
    """Runs the `pip install torch ...` command for the CUDA build in the background."""

    output = pyqtSignal(str)
    finished_install = pyqtSignal(bool)

    def __init__(self, command: str):
        super().__init__()
        self._command = command

    def run(self) -> None:
        import subprocess
        import sys as _sys

        args = self._command.split()
        if args[:1] == ["pip"]:
            # Route through the interpreter CHAOS is actually running under,
            # so the install lands in the right environment.
            args = [_sys.executable, "-m", "pip"] + args[1:]

        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            for line in proc.stdout:
                self.output.emit(line.rstrip())
            proc.wait()
            self.finished_install.emit(proc.returncode == 0)
        except Exception as e:
            self.output.emit(f"Error: {e}")
            self.finished_install.emit(False)


class _HardwareInfoDialog(QDialog):
    """Opens when the hardware badge is clicked: shows CUDA status and, if an
    NVIDIA GPU is present but unused, the steps (or one-click install) to enable it."""

    def __init__(self, system: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GPU Acceleration")
        self.setMinimumWidth(440)
        self._worker: "_CudaInstallWorker | None" = None
        self._command = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        cuda_available = system.get("cuda_available", False)
        gpu_present = system.get("gpu_present", False)
        gpu_name = system.get("gpu_name") or "your GPU"

        if cuda_available:
            title = QLabel("CUDA acceleration is active")
            title.setStyleSheet("font-weight: bold; font-size: 13px; color: #22c55e;")
            layout.addWidget(title)
            body = QLabel(f"Analysis is running on {gpu_name}. No action needed.")
            body.setWordWrap(True)
            layout.addWidget(body)

        elif gpu_present:
            title = QLabel("Enable CUDA for up to 8x faster analysis")
            title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e8963c;")
            layout.addWidget(title)

            driver = system.get("nvidia_driver_version")
            detail = f"Detected {gpu_name}"
            if driver:
                detail += f" (driver {driver})"
            detail += ", but PyTorch is currently running in CPU-only mode."
            detail_lbl = QLabel(detail)
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
            layout.addWidget(detail_lbl)

            self._command = SystemDetector.get_pytorch_install_command(
                system.get("nvidia_max_cuda_version")
            )

            cmd_lbl = QLabel("Required action — reinstall PyTorch with CUDA support:")
            cmd_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            layout.addWidget(cmd_lbl)

            cmd_row = QHBoxLayout()
            cmd_edit = QLineEdit(self._command)
            cmd_edit.setReadOnly(True)
            cmd_row.addWidget(cmd_edit)
            copy_btn = QPushButton("Copy")
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._command))
            cmd_row.addWidget(copy_btn)
            layout.addLayout(cmd_row)

            self._log = QTextEdit()
            self._log.setReadOnly(True)
            self._log.setFixedHeight(120)
            self._log.setVisible(False)
            layout.addWidget(self._log)

            self._install_btn = QPushButton("Install CUDA-enabled PyTorch")
            self._install_btn.clicked.connect(self._start_install)
            layout.addWidget(self._install_btn)

            self._status_lbl = QLabel("")
            self._status_lbl.setWordWrap(True)
            self._status_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            layout.addWidget(self._status_lbl)

        else:
            title = QLabel("No NVIDIA GPU detected")
            title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3;")
            layout.addWidget(title)
            body = QLabel("CHAOS will run on CPU only. This is expected on this hardware.")
            body.setWordWrap(True)
            layout.addWidget(body)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        close_row.addWidget(self._close_btn)
        layout.addLayout(close_row)

    def _start_install(self) -> None:
        self._install_btn.setEnabled(False)
        self._install_btn.setText("Installing…")
        self._close_btn.setEnabled(False)
        self._log.setVisible(True)
        self._log.clear()
        self._status_lbl.setText("")

        self._worker = _CudaInstallWorker(self._command)
        self._worker.output.connect(self._log.append)
        self._worker.finished_install.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_finished(self, success: bool) -> None:
        self._close_btn.setEnabled(True)
        if success:
            self._install_btn.setText("Installed")
            self._status_lbl.setText("Done — restart CHAOS to start using CUDA acceleration.")
            self._status_lbl.setStyleSheet("color: #22c55e; font-size: 11px;")
        else:
            self._install_btn.setEnabled(True)
            self._install_btn.setText("Install CUDA-enabled PyTorch")
            self._status_lbl.setText("Install failed — see log above, or run the command manually.")
            self._status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)


class RunView(QWidget):
    """Run controls, pipeline progress, and log."""

    pipeline_finished = pyqtSignal(bool, int)  # success, input_bytes

    def __init__(self, clip_source: ClipSourceView, config_manager: ConfigManager):
        super().__init__()
        self._source = clip_source
        self.config_manager = config_manager
        self._worker = None
        self._input_size_bytes = 0
        self._worker_target = 2
        self._elapsed_secs = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._build_ui()
        self._refresh_summary()

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

        self._summary_frame = self._build_summary_card()
        root.addWidget(self._summary_frame)

        self._run_btn = QPushButton("FIND HIGHLIGHTS")
        self._run_btn.setObjectName("runButton")
        self._run_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._run_btn.clicked.connect(self._start_pipeline)
        root.addWidget(self._run_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._validation_label = QLabel("")
        self._validation_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self._validation_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._validation_label)

        self._pipeline_widget = AnimatedPipelineWidget()
        self._pipeline_widget.setVisible(False)
        root.addWidget(self._pipeline_widget)

        self._ctrl_frame = self._build_ctrl_row()
        self._ctrl_frame.setVisible(False)
        root.addWidget(self._ctrl_frame)

        self._log_viewer = LogViewer()
        self._log_viewer.setMinimumHeight(150)
        root.addWidget(self._log_viewer)
        root.addStretch()

    def _build_summary_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("summaryCard")
        # Use ID selector so the rule doesn't cascade into child QFrames
        frame.setStyleSheet(
            "#summaryCard { background-color: #12151a; border-radius: 6px; border: 1px solid #2a2d35; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(4)

        # Headline: file count + size, hardware badge flush right
        top = QHBoxLayout()
        self._summary_files_lbl = QLabel("—")
        self._summary_files_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #e6edf3;")
        top.addWidget(self._summary_files_lbl)
        top.addStretch()
        self._hw_badge = QPushButton("CPU only")
        self._hw_badge.setFlat(True)
        self._hw_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hw_badge.setToolTip("Click for GPU acceleration details")
        self._hw_badge.clicked.connect(self._show_hw_info)
        top.addWidget(self._hw_badge)
        layout.addLayout(top)

        # Player names (clearly smaller and muted)
        self._summary_names_lbl = QLabel("No player names configured")
        self._summary_names_lbl.setStyleSheet("font-size: 11px; color: #6b7280;")
        layout.addWidget(self._summary_names_lbl)

        # Footer: output path + open button on left, workers stepper on right
        bot = QHBoxLayout()
        bot.setSpacing(6)

        out_lbl = QLabel("Output:")
        out_lbl.setStyleSheet("font-size: 11px; color: #4b5563;")
        bot.addWidget(out_lbl)

        self._output_path_lbl = QLabel("./final_clips")
        self._output_path_lbl.setStyleSheet("font-size: 11px; color: #6b7280;")
        bot.addWidget(self._output_path_lbl)

        _ICON = (
            "QPushButton { font-size: 10px; color: #4b5563; border: 1px solid #2a2d35; "
            "border-radius: 2px; padding: 0; min-width: 0; min-height: 0; background: transparent; }"
            "QPushButton:hover { color: #9ca3af; border-color: #4b5563; }"
        )
        self._open_output_btn = QPushButton("↗")
        self._open_output_btn.setFixedSize(18, 18)
        self._open_output_btn.setStyleSheet(_ICON)
        self._open_output_btn.setToolTip("Open output folder")
        self._open_output_btn.clicked.connect(self._open_output_folder)
        bot.addWidget(self._open_output_btn)

        bot.addStretch()

        w_lbl = QLabel("Workers:")
        w_lbl.setStyleSheet("font-size: 11px; color: #4b5563;")
        bot.addWidget(w_lbl)

        _STEP = (
            "QPushButton { background: transparent; border: 1px solid #2a2d35; "
            "color: #6b7280; font-size: 12px; border-radius: 2px; "
            "padding: 0; min-width: 0; min-height: 0; }"
            "QPushButton:hover { color: #e8963c; border-color: #e8963c; }"
        )
        self._workers_dec_btn = QPushButton("−")
        self._workers_dec_btn.setFixedSize(18, 18)
        self._workers_dec_btn.setStyleSheet(_STEP)
        self._workers_dec_btn.clicked.connect(self._dec_workers)
        bot.addWidget(self._workers_dec_btn)

        self._workers_count_lbl = QLabel("2")
        self._workers_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._workers_count_lbl.setFixedWidth(22)
        self._workers_count_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #c8ccd4;")
        bot.addWidget(self._workers_count_lbl)

        self._workers_inc_btn = QPushButton("+")
        self._workers_inc_btn.setFixedSize(18, 18)
        self._workers_inc_btn.setStyleSheet(_STEP)
        self._workers_inc_btn.clicked.connect(self._inc_workers)
        bot.addWidget(self._workers_inc_btn)

        layout.addLayout(bot)
        return frame

    def _build_ctrl_row(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_pipeline)
        row.addWidget(self._pause_btn)
        row.addWidget(self._stop_btn)
        row.addSpacing(16)
        self._elapsed_lbl = QLabel("")
        self._elapsed_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        row.addWidget(self._elapsed_lbl)
        return w

    # ------------------------------------------------------------------ public

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        if not self._worker:
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        cfg = self.config_manager.load_config()

        if self._source.is_files_mode():
            file_list = self._source.get_file_list() or []
            count = len(file_list)
            size = sum(os.path.getsize(p) for p in file_list if os.path.exists(p))
        else:
            folder = self._source.get_folder()
            file_list = self._source.get_file_list()
            if file_list is not None:
                count = len(file_list)
                size = sum(os.path.getsize(p) for p in file_list if os.path.exists(p))
            elif folder and os.path.isdir(folder):
                size, count = _folder_video_size(folder)
            else:
                size, count = 0, 0

        if count:
            self._summary_files_lbl.setText(
                f"{count} video{'s' if count != 1 else ''}  ·  {_fmt_size(size)}"
            )
        else:
            self._summary_files_lbl.setText("No files configured")

        names = self._source.get_names()
        if names:
            shown = names[:3]
            rest = len(names) - len(shown)
            text = ", ".join(shown) + (f"  +{rest} more" if rest else "")
            self._summary_names_lbl.setText(text)
        else:
            self._summary_names_lbl.setText("No player names configured")

        self._apply_hw_badge(cfg)

        self._output_path_lbl.setText(cfg.get("final_clips_folder", "./final_clips"))

        nw = cfg.get("pipeline", {}).get("analysis_workers",
             cfg.get("analysis_workers", 2))
        self._worker_target = nw
        self._workers_count_lbl.setText(str(nw))

    # ------------------------------------------------------------------ hardware badge

    def refresh_hw_badge(self) -> None:
        """Re-read CUDA/GPU status from config and update the badge. Called by
        the main window once the background CUDA detection thread finishes."""
        self._apply_hw_badge(self.config_manager.load_config())

    def _apply_hw_badge(self, cfg: dict) -> None:
        system = cfg.get("system", {})
        self._hw_system_info = system

        if system.get("cuda_available"):
            name = system.get("gpu_name") or "GPU"
            self._hw_badge.setText(f"⚡ CUDA · {name}")
            self._hw_badge.setStyleSheet(
                "QPushButton { background: #14291a; color: #22c55e; font-size: 10px; "
                "border: 1px solid #166534; border-radius: 3px; padding: 2px 7px; }"
                "QPushButton:hover { border-color: #22c55e; }"
            )
        elif system.get("gpu_present"):
            self._hw_badge.setText("Enable CUDA for 8x speedup ▸")
            self._hw_badge.setStyleSheet(
                "QPushButton { background: #2a1f0f; color: #e8963c; font-size: 10px; "
                "font-weight: bold; border: 1px solid #e8963c; border-radius: 3px; padding: 2px 7px; }"
                "QPushButton:hover { background: #3a2a12; }"
            )
        else:
            self._hw_badge.setText("CPU only")
            self._hw_badge.setStyleSheet(
                "QPushButton { background: #1c2230; color: #6b7280; font-size: 10px; "
                "border: 1px solid #374151; border-radius: 3px; padding: 2px 7px; }"
                "QPushButton:hover { border-color: #6b7280; }"
            )

    def _show_hw_info(self) -> None:
        system = getattr(self, "_hw_system_info", {}) or {}
        dlg = _HardwareInfoDialog(system, self)
        dlg.exec()
        self.refresh_hw_badge()

    # ------------------------------------------------------------------ workers

    def _dec_workers(self) -> None:
        self._worker_target = max(1, self._worker_target - 1)
        self._workers_count_lbl.setText(str(self._worker_target))

    def _inc_workers(self) -> None:
        self._worker_target += 1
        self._workers_count_lbl.setText(str(self._worker_target))

    # ------------------------------------------------------------------ output folder

    def _open_output_folder(self) -> None:
        import subprocess, sys as _sys
        cfg = self.config_manager.load_config()
        folder = cfg.get("final_clips_folder", "./final_clips")
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        os.makedirs(folder, exist_ok=True)
        if _sys.platform == "win32":
            os.startfile(folder)
        elif _sys.platform == "darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])

    # ------------------------------------------------------------------ elapsed timer

    def _tick_elapsed(self) -> None:
        self._elapsed_secs += 1
        elapsed = self._fmt_duration(self._elapsed_secs)
        done = self._pipeline_widget._done
        total = self._pipeline_widget._total
        eta = ""
        if done > 0 and total > done:
            secs_per = self._elapsed_secs / done
            eta = f"  ·  ETA ~{self._fmt_duration(int(secs_per * (total - done)))}"
        self._elapsed_lbl.setText(f"Elapsed: {elapsed}{eta}")

    @staticmethod
    def _fmt_duration(secs: int) -> str:
        m, s = divmod(secs, 60)
        if m < 60:
            return f"{m}:{s:02d}"
        h, m2 = divmod(m, 60)
        return f"{h}:{m2:02d}:{s:02d}"

    # ------------------------------------------------------------------ run

    def _validate(self) -> str:
        if self._source.is_files_mode():
            if not self._source.get_file_list():
                return "Add at least one video file."
        else:
            if not self._source.get_folder():
                return "Select a folder containing your CS2 clips."
            file_list = self._source.get_file_list()
            if file_list is not None and not file_list:
                return "Select at least one clip to process."
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

        self._pipeline_widget.set_worker_target(self._worker_target)
        self._worker.workers_count_changed.connect(self._pipeline_widget.set_worker_target)
        self._pipeline_widget.workers_changed.connect(self._worker.set_target_workers)

        self._set_running(True)
        self._log_viewer.clear_log()
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
        self._summary_frame.setVisible(not running)
        self._run_btn.setVisible(not running)
        self._validation_label.setVisible(not running)
        self._pipeline_widget.setVisible(running)
        self._ctrl_frame.setVisible(running)
        self._pause_btn.setEnabled(running)
        self._pause_btn.setText("Pause")
        self._stop_btn.setEnabled(running)
        if running:
            self._elapsed_secs = 0
            self._elapsed_lbl.setText("Elapsed: 0:00")
            self._elapsed_timer.start()
        else:
            self._elapsed_timer.stop()
            if self._elapsed_secs > 0:
                self._log_viewer.add_message(
                    f"Completed in {self._fmt_duration(self._elapsed_secs)}", "info"
                )

    def _on_progress(self, pct: int, msg: str) -> None:
        pass
