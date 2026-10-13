"""
Clip source view (folder/file picker + player names) and run view (pipeline + log).
"""

import os
import shutil
import cv2
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi"}

# Relative config paths resolve against the project root, matching PipelineWorker.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Below this much free space on the clips drive, warn before starting a run.
LOW_SPACE_BYTES = 5_000_000_000


def _clips_folder(cfg: dict) -> str:
    folder = cfg.get("final_clips_folder") or "./final_clips"
    if not os.path.isabs(folder):
        folder = str((_PROJECT_ROOT / folder).resolve())
    return folder


def _free_bytes(path: str) -> "int | None":
    """Free space on the drive holding path. Walks up to the nearest existing
    ancestor since the clips folder may not have been created yet."""
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return None


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
    QStackedWidget, QFrame, QSizePolicy, QScrollArea, QGridLayout, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from desktop_app.gui.widgets.log_viewer import LogViewer
from desktop_app.gui.widgets.animated_pipeline import AnimatedPipelineWidget
from desktop_app.workers.pipeline_worker import PipelineWorker
from chaos_lib.resources import plan_analysis_workers
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


class _HoverPreviewWorker(QThread):
    """Plays an entire clip back at accelerated speed for a hover preview.

    Uses grab()/retrieve() to skip frames cheaply (no decode) and only decodes
    the sampled frame, sleeping one source-frame-interval between samples so
    `step` frames of footage pass per real frame tick — i.e. `step`x speed.

    Frames are emitted at a moderate resolution (not the tiny thumbnail size)
    so the card can both render the small thumbnail and let the zoom panel
    crop a magnified region out of the same frame with reasonable detail.
    """

    frame_ready = pyqtSignal(QImage)

    _PREVIEW_MAX_W = 800

    def __init__(self, path: str, speed: float = 10.0):
        super().__init__()
        self._path = path
        self._speed = speed
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            return
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total <= 0:
                return
            step = max(1, round(self._speed))
            interval_ms = max(1, int(1000 / fps))

            while not self._stopped:
                idx = 0
                while not self._stopped and idx < total:
                    if not cap.grab():
                        break
                    if idx % step == 0:
                        ret, frame = cap.retrieve()
                        if ret:
                            img = self._to_qimage(frame)
                            if img is not None:
                                self.frame_ready.emit(img)
                        self.msleep(interval_ms)
                    idx += 1
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop while still hovered
        finally:
            cap.release()

    def _to_qimage(self, frame) -> "QImage | None":
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            img = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888).copy()
            if w > self._PREVIEW_MAX_W:
                img = img.scaledToWidth(self._PREVIEW_MAX_W, Qt.TransformationMode.SmoothTransformation)
            return img
        except Exception:
            return None


class _ThumbLabel(QLabel):
    """Thumbnail image label that can draw a bounding rectangle over the
    region currently shown magnified in the zoom preview panel."""

    def __init__(self):
        super().__init__()
        self._zoom_rect: "QRectF | None" = None

    def set_zoom_rect(self, rect: "QRectF | None") -> None:
        self._zoom_rect = rect
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._zoom_rect is None:
            return
        painter = QPainter(self)
        pen = QPen(QColor("#e8963c"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self._zoom_rect)


class _ThumbnailCard(QFrame):
    """Single clip card: thumbnail image + filename. Click to toggle selection.

    Hovering plays the whole clip back at 10x speed in place of the static
    thumbnail; moving off restores the static frame.
    """

    toggled = pyqtSignal(str, bool)  # path, selected
    zoom_updated = pyqtSignal(QImage)  # magnified crop centered on the cursor
    zoom_ended = pyqtSignal()  # mouse left the card; clear the zoom panel

    _ZOOM_FACTOR = 4.0
    _ZOOM_OUT_W = 320  # matches _ZoomPreviewPanel's default size 1:1, no label scaling needed
    _ZOOM_OUT_H = 180

    def __init__(self, path: str, tw: int, th: int):
        super().__init__()
        self._path = path
        self._selected = True
        self._tw, self._th = tw, th
        self._thumb_pixmap: "QPixmap | None" = None
        self._preview_worker: "_HoverPreviewWorker | None" = None
        self._last_full_frame: "QImage | None" = None
        self._rel_pos: "tuple[float, float] | None" = None
        self.setObjectName("thumbCard")
        self.setFixedWidth(tw + 8)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self._img = _ThumbLabel()
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
        self._thumb_pixmap = QPixmap.fromImage(img)
        if self._preview_worker is None:
            self._img.setPixmap(self._thumb_pixmap)

    def enterEvent(self, event) -> None:
        self._start_preview()
        self._handle_hover_pos(self._pos_from_event(event))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._stop_preview()
        self._rel_pos = None
        self._last_full_frame = None
        self._img.set_zoom_rect(None)
        self.zoom_ended.emit()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self._handle_hover_pos(self._pos_from_event(event))
        super().mouseMoveEvent(event)

    def stop_preview(self) -> None:
        """Called by the grid before this card is torn down."""
        self._stop_preview()

    def _pos_from_event(self, event):
        return self._img.mapFromGlobal(event.globalPosition().toPoint())

    def _start_preview(self) -> None:
        if self._preview_worker is not None or not os.path.isfile(self._path):
            return
        worker = _HoverPreviewWorker(self._path)
        worker.frame_ready.connect(self._on_preview_frame)
        self._preview_worker = worker
        worker.start()

    def _stop_preview(self) -> None:
        # Stop and *wait* for the thread to fully exit (releasing its
        # cv2.VideoCapture) before returning. Without this, rapidly hovering
        # between cards piles up multiple decoder threads/handles on the same
        # process (and can destroy a still-running QThread on GC), which is
        # what was crashing the app after a few hovers.
        worker = self._preview_worker
        self._preview_worker = None
        if worker is not None:
            try:
                worker.frame_ready.disconnect(self._on_preview_frame)
            except TypeError:
                pass
            worker.stop()
            worker.wait()
        if self._thumb_pixmap is not None:
            self._img.setPixmap(self._thumb_pixmap)
        else:
            self._img.setText("…")

    def _on_preview_frame(self, img: QImage) -> None:
        self._last_full_frame = img
        thumb = img.scaled(
            self._tw, self._th,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._img.setPixmap(QPixmap.fromImage(thumb))
        if self._rel_pos is not None:
            self._emit_zoom()

    def _handle_hover_pos(self, local_pos) -> None:
        w, h = self._img.width(), self._img.height()
        if w <= 0 or h <= 0:
            return
        rel_x = min(max(local_pos.x() / w, 0.0), 1.0)
        rel_y = min(max(local_pos.y() / h, 0.0), 1.0)
        self._rel_pos = (rel_x, rel_y)
        self._update_overlay_rect()
        self._emit_zoom()

    def _update_overlay_rect(self) -> None:
        if self._rel_pos is None:
            self._img.set_zoom_rect(None)
            return
        rel_x, rel_y = self._rel_pos
        w, h = float(self._tw), float(self._th)
        rw, rh = w / self._ZOOM_FACTOR, h / self._ZOOM_FACTOR
        x0 = min(max(rel_x * w - rw / 2, 0.0), w - rw)
        y0 = min(max(rel_y * h - rh / 2, 0.0), h - rh)
        self._img.set_zoom_rect(QRectF(x0, y0, rw, rh))

    def _emit_zoom(self) -> None:
        if self._last_full_frame is None or self._rel_pos is None:
            return
        rel_x, rel_y = self._rel_pos
        fw, fh = float(self._last_full_frame.width()), float(self._last_full_frame.height())
        if fw <= 0 or fh <= 0:
            return
        cw, ch = fw / self._ZOOM_FACTOR, fh / self._ZOOM_FACTOR
        x0 = min(max(rel_x * fw - cw / 2, 0.0), fw - cw)
        y0 = min(max(rel_y * fh - ch / 2, 0.0), fh - ch)
        crop = self._last_full_frame.copy(int(x0), int(y0), int(cw), int(ch))
        scaled = crop.scaled(
            self._ZOOM_OUT_W, self._ZOOM_OUT_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.zoom_updated.emit(scaled)

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
    zoom_updated = pyqtSignal(QImage)
    zoom_ended = pyqtSignal()

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
            widget = item.widget()
            if widget:
                if isinstance(widget, _ThumbnailCard):
                    widget.stop_preview()
                widget.deleteLater()
        self._cards.clear()

        if not paths:
            self.setVisible(False)
            return

        for i, path in enumerate(paths):
            card = _ThumbnailCard(path, self._TW, self._TH)
            card.toggled.connect(self._on_card_toggled)
            card.zoom_updated.connect(self.zoom_updated)
            card.zoom_ended.connect(self.zoom_ended)
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

    def select_all(self) -> None:
        for card in self._cards.values():
            card.set_selected(True, emit=False)
        self.selection_changed.emit()

    def deselect_all(self) -> None:
        for card in self._cards.values():
            card.set_selected(False, emit=False)
        self.selection_changed.emit()


class _ZoomPreviewPanel(QFrame):
    """Right-side panel showing a magnified crop of whichever clip is hovered,
    centered on the mouse position (see _ThumbnailCard._emit_zoom)."""

    def __init__(self, width: int = 320, height: int = 180):
        super().__init__()
        self.setFixedSize(width, height)
        self.setStyleSheet(
            "QFrame { background: #0d0f14; border: 1px solid #2a2d35; border-radius: 4px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("Hover a clip to zoom in")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: #374151; font-size: 11px; border: none;")
        layout.addWidget(self._label)

    def set_image(self, img: QImage) -> None:
        self._label.setText("")
        self._label.setPixmap(QPixmap.fromImage(img))

    def clear(self) -> None:
        self._label.setPixmap(QPixmap())
        self._label.setText("Hover a clip to zoom in")


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

        size_row = QHBoxLayout()
        self._folder_size_lbl = QLabel("")
        self._folder_size_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        size_row.addWidget(self._folder_size_lbl)
        size_row.addStretch()

        self._select_toggle_btn = QPushButton("Deselect all")
        self._select_toggle_btn.setVisible(False)
        self._select_toggle_btn.clicked.connect(self._on_select_toggle_clicked)
        size_row.addWidget(self._select_toggle_btn)

        layout.addLayout(size_row)

        grid_row = QHBoxLayout()
        grid_row.setSpacing(10)

        self._thumb_grid = ClipThumbnailGrid()
        self._thumb_grid.selection_changed.connect(self._on_clip_selection_changed)
        grid_row.addWidget(self._thumb_grid, 1)

        self._zoom_panel = _ZoomPreviewPanel()
        self._thumb_grid.zoom_updated.connect(self._zoom_panel.set_image)
        self._thumb_grid.zoom_ended.connect(self._zoom_panel.clear)
        grid_row.addWidget(self._zoom_panel, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(grid_row, 1)

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
        self._select_toggle_btn.setVisible(bool(count))
        self._select_toggle_btn.setText("Deselect all")

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
        self._select_toggle_btn.setText("Select all" if not selected else "Deselect all")

    def _on_select_toggle_clicked(self) -> None:
        if self._thumb_grid.get_selected_paths():
            self._thumb_grid.deselect_all()
        else:
            self._thumb_grid.select_all()

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
        self.setMinimumWidth(560)
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
            detail = f"CHAOS found {gpu_name}"
            if driver:
                detail += f" (driver {driver})"
            detail += ", but it isn't being used. The version of PyTorch currently installed is CPU-only."
            detail_lbl = QLabel(detail)
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
            layout.addWidget(detail_lbl)

            self._command = SystemDetector.get_pytorch_install_command(
                system.get("nvidia_max_cuda_version")
            )

            install_intro = QLabel(
                "Recommended: click the button below and CHAOS will download and install the "
                "CUDA build of PyTorch for you (roughly 2 to 3 GB, can take a few minutes on a "
                "typical connection). It replaces the CPU-only version currently installed."
            )
            install_intro.setWordWrap(True)
            install_intro.setStyleSheet("color: #9ca3af; font-size: 12px;")
            layout.addWidget(install_intro)

            self._install_btn = QPushButton("Install CUDA-enabled PyTorch")
            self._install_btn.clicked.connect(self._start_install)
            layout.addWidget(self._install_btn)

            self._log = QTextEdit()
            self._log.setReadOnly(True)
            self._log.setFixedHeight(120)
            self._log.setVisible(False)
            layout.addWidget(self._log)

            self._status_lbl = QLabel("")
            self._status_lbl.setWordWrap(True)
            self._status_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            self._status_lbl.setVisible(False)
            layout.addWidget(self._status_lbl)

            self._restart_btn = QPushButton("Restart Now")
            self._restart_btn.setVisible(False)
            self._restart_btn.clicked.connect(self._restart_app)
            layout.addWidget(self._restart_btn)

            manual_lbl = QLabel("Prefer to do it yourself? Copy this command and run it in a terminal:")
            manual_lbl.setWordWrap(True)
            manual_lbl.setStyleSheet("color: #6b7280; font-size: 11px; margin-top: 6px;")
            layout.addWidget(manual_lbl)

            cmd_row = QHBoxLayout()
            cmd_edit = QLineEdit(self._command)
            cmd_edit.setReadOnly(True)
            cmd_edit.setToolTip(self._command)
            cmd_edit.setCursorPosition(0)
            cmd_row.addWidget(cmd_edit)
            copy_btn = QPushButton("Copy")
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._command))
            cmd_row.addWidget(copy_btn)
            layout.addLayout(cmd_row)

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
        self._status_lbl.setVisible(False)

        self._worker = _CudaInstallWorker(self._command)
        self._worker.output.connect(self._log.append)
        self._worker.finished_install.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_finished(self, success: bool) -> None:
        self._close_btn.setEnabled(True)
        if success:
            self._install_btn.setText("Installed")
            self._status_lbl.setText("Done. Restart CHAOS to start using CUDA acceleration.")
            self._status_lbl.setStyleSheet("color: #22c55e; font-size: 11px;")
            self._status_lbl.setVisible(True)
            self._restart_btn.setVisible(True)
        else:
            self._install_btn.setEnabled(True)
            self._install_btn.setText("Install CUDA-enabled PyTorch")
            self._status_lbl.setText("Install failed. See the log above, or run the command manually.")
            self._status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")
            self._status_lbl.setVisible(True)

    def _restart_app(self) -> None:
        import subprocess
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        launcher = repo_root / "run_desktop_app.py"
        subprocess.Popen([sys.executable, str(launcher)], cwd=str(repo_root))
        QApplication.instance().quit()

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
        self._auto_workers = False
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
        self._summary_names_lbl = QLabel("Player name read from each video's killfeed")
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

        self._output_free_lbl = QLabel("")
        self._output_free_lbl.setStyleSheet("font-size: 11px; color: #4b5563;")
        bot.addWidget(self._output_free_lbl)

        _ICON = (
            "QPushButton { font-size: 10px; color: #4b5563; border: 1px solid #2a2d35; "
            "border-radius: 2px; padding: 2px; min-width: 0; min-height: 0; background: transparent; }"
            "QPushButton:hover { color: #9ca3af; border-color: #4b5563; }"
        )
        self._change_output_btn = QPushButton("Change…")
        self._change_output_btn.setFixedHeight(22)
        self._change_output_btn.setStyleSheet(_ICON + "QPushButton { padding: 2px 6px; }")
        self._change_output_btn.setToolTip("Choose where finished clips are saved")
        self._change_output_btn.clicked.connect(self._choose_output_folder)
        bot.addWidget(self._change_output_btn)

        self._open_output_btn = QPushButton("↗")
        self._open_output_btn.setFixedSize(22, 22)
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
            "padding: 2px; min-width: 0; min-height: 0; }"
            "QPushButton:hover { color: #e8963c; border-color: #e8963c; }"
        )
        self._workers_dec_btn = QPushButton("−")
        self._workers_dec_btn.setFixedSize(22, 22)
        self._workers_dec_btn.setStyleSheet(_STEP)
        self._workers_dec_btn.clicked.connect(self._dec_workers)
        bot.addWidget(self._workers_dec_btn)

        # Grows to fit "auto"; the minimum keeps the stepper from jumping for 1-2 digits
        self._workers_count_lbl = QLabel("2")
        self._workers_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._workers_count_lbl.setMinimumWidth(22)
        self._workers_count_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #c8ccd4; padding: 0 4px;"
        )
        bot.addWidget(self._workers_count_lbl)

        self._workers_inc_btn = QPushButton("+")
        self._workers_inc_btn.setFixedSize(22, 22)
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
        self._gaming_btn = QPushButton("🎮 I'm playing, go easy on my GPU")
        self._gaming_btn.setCheckable(True)
        self._gaming_btn.setToolTip(
            "Throttle analysis so your game keeps its frame rate.\n"
            "Drops to one worker at idle priority that rests most of the time.\n"
            "Click again when you're done playing to go back to full speed."
        )
        self._gaming_btn.setStyleSheet("QPushButton:checked { color: #22c55e; border-color: #166534; }")
        self._gaming_btn.toggled.connect(self._toggle_gaming)
        row.addWidget(self._pause_btn)
        row.addWidget(self._stop_btn)
        row.addWidget(self._gaming_btn)
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
            self._summary_names_lbl.setText("Player name read from each video's killfeed")

        self._apply_hw_badge(cfg)

        self._refresh_output_folder(cfg)

        nw = cfg.get("pipeline", {}).get("analysis_workers",
             cfg.get("analysis_workers", "auto"))
        # None = auto: the worker sizes the pool from free VRAM/RAM at start.
        self._worker_target = nw if isinstance(nw, int) and nw > 0 else None
        self._workers_count_lbl.setText(str(self._worker_target or "auto"))
        self._workers_count_lbl.setToolTip(
            "auto: when the run starts, uses as many workers as fit in free GPU memory and RAM"
        )

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

    def _plan(self):
        return plan_analysis_workers(self.config_manager.load_config())

    def _dec_workers(self) -> None:
        current = self._worker_target or self._plan().workers
        self._worker_target = max(1, current - 1)
        self._workers_count_lbl.setText(str(self._worker_target))

    def _inc_workers(self) -> None:
        plan = self._plan()
        current = self._worker_target or plan.workers
        # Past the plan's max the workers wouldn't fit in VRAM/RAM: back to auto.
        self._worker_target = current + 1 if current < plan.max_workers else None
        self._workers_count_lbl.setText(str(self._worker_target or "auto"))
        self._workers_count_lbl.setToolTip(plan.summary)

    # ------------------------------------------------------------------ output folder

    def _refresh_output_folder(self, cfg: dict) -> None:
        folder = _clips_folder(cfg)
        metrics = self._output_path_lbl.fontMetrics()
        self._output_path_lbl.setText(
            metrics.elidedText(folder, Qt.TextElideMode.ElideMiddle, 320))
        self._output_path_lbl.setToolTip(folder)

        free = _free_bytes(folder)
        if free is None:
            self._output_free_lbl.setText("")
            return
        low = free < LOW_SPACE_BYTES
        self._output_free_lbl.setText(f"·  {_fmt_size(free)} free")
        self._output_free_lbl.setStyleSheet(
            f"font-size: 11px; color: {'#e8963c' if low else '#4b5563'};"
            + (" font-weight: bold;" if low else ""))
        self._output_free_lbl.setToolTip(
            "Low disk space on this drive. Pick a folder on a drive with more room."
            if low else "")

    def _choose_output_folder(self) -> bool:
        """Let the user pick the clips folder and save it. True if one was chosen."""
        cfg = self.config_manager.load_config()
        path = QFileDialog.getExistingDirectory(
            self, "Choose where to save finished clips", _clips_folder(cfg))
        if not path:
            return False
        cfg["final_clips_folder"] = path
        self.config_manager.save_config(cfg)
        self._refresh_output_folder(cfg)
        return True

    def _confirm_output_space(self) -> bool:
        """Warn when the clips drive is nearly full. False cancels the run."""
        while True:
            folder = _clips_folder(self.config_manager.load_config())
            free = _free_bytes(folder)
            if free is None or free >= LOW_SPACE_BYTES:
                return True
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Low disk space")
            box.setText(f"Only {_fmt_size(free)} free on the drive for:\n{folder}")
            box.setInformativeText(
                "Clips may fail to save if the drive fills up. "
                "Choose a folder on a drive with more room?")
            change = box.addButton("Change folder…", QMessageBox.ButtonRole.AcceptRole)
            run = box.addButton("Run anyway", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(change)
            box.exec()
            clicked = box.clickedButton()
            if clicked is run:
                return True
            if clicked is not change or not self._choose_output_folder():
                return False
            # Loop to re-check the newly chosen drive.

    def _open_output_folder(self) -> None:
        import subprocess, sys as _sys
        folder = _clips_folder(self.config_manager.load_config())
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

        if not self._confirm_output_space():
            return

        file_list = self._source.get_file_list()

        if file_list:
            self._input_size_bytes = sum(os.path.getsize(p) for p in file_list if os.path.exists(p))
            video_count = len(file_list)
        else:
            folder = self._source.get_folder()
            self._input_size_bytes, video_count = _folder_video_size(folder)

        self._worker = PipelineWorker(stages=ALL_STAGES, file_list=file_list,
                                      requested_workers=self._worker_target)
        if self._gaming_btn.isChecked():
            self._worker.set_gaming_mode(True)

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

        # Until the user steps the count, an "auto" run says so next to it.
        self._auto_workers = self._worker_target is None
        self._pipeline_widget.set_worker_target(self._worker_target or 1, self._worker_note())
        self._worker.workers_count_changed.connect(
            lambda n: self._pipeline_widget.set_worker_target(n, self._worker_note()))
        # Connected before the worker's slot so a clamp it reports back is no longer labelled auto
        self._pipeline_widget.workers_changed.connect(self._on_workers_stepped)
        self._pipeline_widget.workers_changed.connect(self._worker.set_target_workers)

        self._set_running(True)
        self._log_viewer.clear_log()
        self._worker.start()

    def _worker_note(self) -> str:
        if self._gaming_btn.isChecked():
            return "gaming"
        return "auto" if self._auto_workers else ""

    def _on_workers_stepped(self, _n: int) -> None:
        self._auto_workers = False

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

    def _toggle_gaming(self, on: bool):
        self._gaming_btn.setText("🎮 Playing: throttled (click when done)" if on
                                 else "🎮 I'm playing, go easy on my GPU")
        if self._worker:
            self._worker.set_gaming_mode(on)

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
