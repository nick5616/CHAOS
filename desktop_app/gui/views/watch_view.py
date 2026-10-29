"""
Watch view — sequence player with drag-to-reorder timeline and FFmpeg export.
"""

import os
import cv2
import glob
import json
import tempfile
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QFrame,
    QFileDialog, QMessageBox, QSizePolicy, QStyledItemDelegate,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, QSize, QThread, QEvent, QRect, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QImage, QPainter, QPen, QColor, QBrush

from desktop_app.gui.widgets.clip_preview import ClipPreviewWidget
from desktop_app.gui.utils.config_manager import ConfigManager

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi"}
PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 1
CARD_W, CARD_H = 168, 120
BAR_H = 5


# ------------------------------------------------------------------ helpers

def _make_thumbnail(path: str, w: int = 160, h: int = 90) -> QIcon:
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return QIcon()
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(total * 0.1)))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return QIcon()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fh, fw = frame_rgb.shape[:2]
        img = QImage(frame_rgb.tobytes(), fw, fh, 3 * fw, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(img).scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QIcon(pixmap)
    except Exception:
        return QIcon()


# ------------------------------------------------------------------ thumbnail worker

class _ThumbnailLoaderWorker(QThread):
    """Load thumbnails for a list of video paths in a background thread."""
    thumbnail_ready = pyqtSignal(str, QIcon)   # path, icon

    def __init__(self, paths: list, cache: dict, w: int = 160, h: int = 90):
        super().__init__()
        self._paths  = paths
        self._cache  = cache
        self._w, self._h = w, h
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for path in self._paths:
            if self._cancelled:
                break
            if path in self._cache:
                self.thumbnail_ready.emit(path, self._cache[path])
                continue
            icon = _make_thumbnail(path, self._w, self._h)
            self._cache[path] = icon
            self.thumbnail_ready.emit(path, icon)


# ------------------------------------------------------------------ delegate

class ClipCardDelegate(QStyledItemDelegate):
    """Draws a progress bar at the bottom of each timeline card."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)

        progress = index.data(PROGRESS_ROLE)
        if progress is None:
            return

        r = option.rect
        track = QRect(r.left() + 1, r.bottom() - BAR_H, r.width() - 2, BAR_H)

        painter.save()
        painter.fillRect(track, QColor("#1a1d23"))

        fill = max(0.0, min(1.0, float(progress)))
        if fill > 0.0:
            fill_rect = QRect(track.left(), track.top(), int(track.width() * fill), track.height())
            painter.fillRect(fill_rect, QColor("#e8963c"))
        painter.restore()


# ------------------------------------------------------------------ drop overlay

class _DropOverlay(QWidget):
    """Transparent overlay drawn on top of the timeline viewport."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._rect = QRect()
        self.hide()

    def set_rect(self, rect: QRect):
        self._rect = rect
        if rect.isNull():
            self.hide()
        else:
            self.show()
            self.raise_()
        self.update()

    def paintEvent(self, event):
        if self._rect.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#e8963c"), 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(232, 150, 60, 30)))
        p.drawRoundedRect(self._rect.adjusted(3, 3, -3, -3), 5, 5)


# ------------------------------------------------------------------ custom list

class _TimelineWidget(QListWidget):
    """QListWidget with dashed drop-placeholder and no item spacing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay = _DropOverlay(self.viewport())
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QEvent.Type.Resize:
            self._overlay.resize(self.viewport().size())
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        self._update_overlay(event.position().toPoint())

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self._overlay.set_rect(QRect())

    def dropEvent(self, event):
        self._overlay.set_rect(QRect())
        super().dropEvent(event)

    def _update_overlay(self, pos):
        self._overlay.resize(self.viewport().size())
        item = self.itemAt(pos)
        if item:
            rect = self.visualItemRect(item)
        elif self.count() > 0:
            last = self.visualItemRect(self.item(self.count() - 1))
            rect = last.translated(last.width(), 0)
        else:
            rect = QRect()
        self._overlay.set_rect(rect)


# ------------------------------------------------------------------ export worker

class _ExportWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, clip_paths: list, output_path: str):
        super().__init__()
        self.clip_paths = clip_paths
        self.output_path = output_path

    def run(self):
        concat_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                concat_file = f.name
                for path in self.clip_paths:
                    f.write(f"file '{path.replace(chr(92), chr(47))}'\n")

            from chaos_lib.clipper import _get_ffmpeg
            result = subprocess.run(
                [_get_ffmpeg(), "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_file, "-c", "copy", self.output_path],
                capture_output=True, text=True,
            )

            if result.returncode == 0:
                self.finished.emit(True, self.output_path)
            else:
                self.finished.emit(False, (result.stderr or result.stdout)[-600:])
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            if concat_file and os.path.exists(concat_file):
                try:
                    os.unlink(concat_file)
                except OSError:
                    pass


# ------------------------------------------------------------------ main view

class WatchView(QWidget):
    """Watch clips in sequence, drag to reorder, export as one stitched video."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._current_index = -1
        self._playing_sequence = False
        self._updating_timeline = False
        self._export_worker = None
        self._thumb_cache: dict = {}
        self._thumb_worker: _ThumbnailLoaderWorker | None = None
        self._dirty = True          # reload on first switch; set again after pipeline runs
        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Controls bar
        # ID selectors so the border doesn't cascade into the labels (QLabel is a QFrame)
        ctrl_bar = QFrame()
        ctrl_bar.setObjectName("watchCtrlBar")
        ctrl_bar.setStyleSheet(
            "#watchCtrlBar { background: #12151a; border-bottom: 1px solid #2a2d35; }"
        )
        ctrl_bar.setFixedHeight(52)
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(16, 0, 16, 0)
        ctrl_layout.setSpacing(8)

        _small = "QPushButton { font-size: 12px; padding: 5px 12px; min-width: 0; }"
        self._prev_btn = QPushButton("◀  Prev")
        self._prev_btn.setStyleSheet(_small)
        self._prev_btn.clicked.connect(self._prev_clip)
        ctrl_layout.addWidget(self._prev_btn)

        # Accent-coloured like the run button, but sized to fit the bar
        self._play_seq_btn = QPushButton("▶  Play All")
        self._play_seq_btn.setStyleSheet(
            "QPushButton { background: #e8963c; color: #0f1014; border: none; border-radius: 4px;"
            " font-size: 12px; font-weight: bold; padding: 6px 18px; min-width: 0; }"
            "QPushButton:hover { background: #d4822a; color: #0f1014; }"
            "QPushButton:disabled { background: #2a2d35; color: #4a4d55; }"
        )
        self._play_seq_btn.clicked.connect(self._toggle_sequence)
        ctrl_layout.addWidget(self._play_seq_btn)

        self._next_btn = QPushButton("Next  ▶")
        self._next_btn.setStyleSheet(_small)
        self._next_btn.clicked.connect(self._next_clip)
        ctrl_layout.addWidget(self._next_btn)

        ctrl_layout.addSpacing(12)

        self._clip_label = QLabel("No clips loaded. Run the pipeline first.")
        self._clip_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        ctrl_layout.addWidget(self._clip_label, 1)

        self._export_btn = QPushButton("Export as one video…")
        self._export_btn.setStyleSheet(_small)
        self._export_btn.setToolTip("Join the clips in timeline order into a single MP4")
        self._export_btn.clicked.connect(self._export_sequence)
        ctrl_layout.addWidget(self._export_btn)

        root.addWidget(ctrl_bar)

        # Video player, inset so its controls don't touch the window edges
        player_box = QWidget()
        player_layout = QVBoxLayout(player_box)
        player_layout.setContentsMargins(16, 12, 16, 10)
        self._preview = ClipPreviewWidget()
        self._preview.clip_ended.connect(self._on_clip_ended)
        self._preview.player.positionChanged.connect(self._on_player_position)
        player_layout.addWidget(self._preview)
        root.addWidget(player_box, 1)

        # Timeline
        tl_frame = QFrame()
        tl_frame.setObjectName("watchTimeline")
        tl_frame.setStyleSheet(
            "#watchTimeline { background: #0f1014; border-top: 1px solid #2a2d35; }"
        )
        tl_layout = QVBoxLayout(tl_frame)
        tl_layout.setContentsMargins(16, 8, 16, 6)
        tl_layout.setSpacing(4)

        tl_header = QLabel("TIMELINE    <span style='color:#4b5563; font-weight:normal;"
                           " letter-spacing:0'>Drag clips to change the order.</span>")
        tl_header.setStyleSheet("color: #6b7280; font-size: 10px; font-weight: bold;"
                                " letter-spacing: 2px; background: transparent;")
        tl_layout.addWidget(tl_header)

        self._timeline = _TimelineWidget()
        self._timeline.setFlow(QListWidget.Flow.LeftToRight)
        self._timeline.setViewMode(QListWidget.ViewMode.IconMode)
        self._timeline.setWrapping(False)
        self._timeline.setResizeMode(QListWidget.ResizeMode.Fixed)
        self._timeline.setMovement(QListWidget.Movement.Snap)
        self._timeline.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._timeline.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._timeline.setIconSize(QSize(160, 88))
        self._timeline.setGridSize(QSize(CARD_W, CARD_H))
        self._timeline.setSpacing(0)
        self._timeline.setUniformItemSizes(True)
        self._timeline.setFixedHeight(CARD_H + 24)
        self._timeline.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._timeline.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._timeline.setItemDelegate(ClipCardDelegate(self._timeline))
        self._timeline.setStyleSheet(
            "QListWidget { background: #0f1014; border: none; }"
            "QListWidget::item { background: #1a1d23; border: 1px solid #2a2d35;"
            "  border-radius: 3px; color: #c8ccd4; margin: 1px; }"
            "QListWidget::item:selected { background: #2a2d35; border-color: #e8963c; }"
            "QListWidget::item:hover { background: #22262e; }"
        )
        self._timeline.currentRowChanged.connect(self._on_timeline_row_changed)
        self._timeline.model().rowsMoved.connect(self._sync_current_index)
        tl_layout.addWidget(self._timeline)

        tl_frame.setFixedHeight(CARD_H + 48)
        root.addWidget(tl_frame)

    # ------------------------------------------------------------------ load

    def mark_dirty(self) -> None:
        """Call after pipeline finishes so next switch reloads clips."""
        self._dirty = True

    def load_clips(self):
        if not self._dirty:
            return
        self._dirty = False
        try:
            config = self.config_manager.load_config()
            clips_folder = self.config_manager.resolve_path(
                config.get("final_clips_folder", "./final_clips")
            )
            data_folder = self.config_manager.resolve_path(
                config.get("data_folder", "./data")
            )
            highlights_path = os.path.join(data_folder, "ordered_highlights.json")

            entries = []

            if os.path.exists(highlights_path):
                with open(highlights_path, "r") as f:
                    highlights = json.load(f)

                for i, clip in enumerate(highlights):
                    score = clip.get("score", 0)
                    path = None
                    # clip_filename is recorded when the clip is cut. Clips are
                    # cut as each video finishes, not in rank order, so the
                    # rank-number pattern is only a fallback for old results.
                    clip_filename = clip.get("clip_filename")
                    if clip_filename:
                        candidate = os.path.join(clips_folder, clip_filename)
                        path = candidate if os.path.exists(candidate) else None
                    else:
                        for pattern in [
                            os.path.join(clips_folder, f"{i+1}_{score}_*.mp4"),
                            os.path.join(clips_folder, f"{i+1}_*.mp4"),
                        ]:
                            matches = glob.glob(pattern)
                            if matches:
                                path = matches[0]
                                break
                    if path:
                        entries.append({
                            "path": path,
                            "label": f"#{i+1:02d}  ·  {score}pts",
                        })
            elif os.path.isdir(clips_folder):
                for name in sorted(os.listdir(clips_folder)):
                    if os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                        entries.append({
                            "path": os.path.join(clips_folder, name),
                            "label": os.path.splitext(name)[0],
                        })

            self._populate_timeline(entries)
        except Exception as e:
            self._clip_label.setText(f"Error loading clips: {e}")

    def _populate_timeline(self, entries: list):
        # Cancel any in-progress thumbnail worker
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.cancel()
            self._thumb_worker.wait()

        self._updating_timeline = True
        self._timeline.clear()
        self._updating_timeline = False
        self._current_index = -1

        # Add items immediately with cached icons (empty placeholder for uncached)
        for entry in entries:
            icon = self._thumb_cache.get(entry["path"], QIcon())
            item = QListWidgetItem(icon, entry["label"])
            item.setData(Qt.ItemDataRole.UserRole, entry["path"])
            item.setData(PROGRESS_ROLE, 0.0)
            item.setSizeHint(QSize(CARD_W, CARD_H))
            self._timeline.addItem(item)

        count = self._timeline.count()
        if count:
            self._clip_label.setText(f"{count} clip{'s' if count != 1 else ''}")
            self._select_clip(0)

            # Load thumbnails in background; already-cached ones emit immediately
            paths = [e["path"] for e in entries]
            self._thumb_worker = _ThumbnailLoaderWorker(paths, self._thumb_cache)
            self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
            self._thumb_worker.start()
        else:
            self._clip_label.setText("No clips found. Run the pipeline first.")

    def _on_thumbnail_ready(self, path: str, icon: QIcon) -> None:
        for i in range(self._timeline.count()):
            item = self._timeline.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                item.setIcon(icon)
                break

    def _select_clip(self, index: int):
        if not (0 <= index < self._timeline.count()):
            return
        self._current_index = index
        self._updating_timeline = True
        self._timeline.setCurrentRow(index)
        self._updating_timeline = False
        self._timeline.scrollToItem(self._timeline.item(index))

        path = self._timeline.item(index).data(Qt.ItemDataRole.UserRole)
        self._preview.load_clip(path)

        self._update_timeline_progress(0.0)

        total = self._timeline.count()
        label = self._timeline.item(index).text()
        self._clip_label.setText(f"{label}  ({index + 1}/{total})")

    # ------------------------------------------------------------------ progress

    def _on_player_position(self, pos_ms: int):
        dur = self._preview.player.duration()
        progress = (pos_ms / dur) if dur > 0 else 0.0
        self._update_timeline_progress(progress)

    def _update_timeline_progress(self, current_progress: float):
        for i in range(self._timeline.count()):
            item = self._timeline.item(i)
            if i < self._current_index:
                item.setData(PROGRESS_ROLE, 1.0)
            elif i == self._current_index:
                item.setData(PROGRESS_ROLE, current_progress)
            else:
                item.setData(PROGRESS_ROLE, 0.0)
        self._timeline.viewport().update()

    # ------------------------------------------------------------------ timeline

    def _on_timeline_row_changed(self, row: int):
        if self._updating_timeline or row < 0 or row == self._current_index:
            return
        self._stop_sequence()
        self._select_clip(row)

    def _sync_current_index(self, *_):
        if not self._preview.clip_path:
            return
        for i in range(self._timeline.count()):
            if self._timeline.item(i).data(Qt.ItemDataRole.UserRole) == self._preview.clip_path:
                self._current_index = i
                self._update_timeline_progress(
                    self._preview.player.position() / max(1, self._preview.player.duration())
                )
                return

    # ------------------------------------------------------------------ controls

    def _prev_clip(self):
        self._stop_sequence()
        self._select_clip(self._current_index - 1)

    def _next_clip(self):
        self._stop_sequence()
        self._select_clip(self._current_index + 1)

    def _toggle_sequence(self):
        if self._playing_sequence:
            self._stop_sequence()
        else:
            self._playing_sequence = True
            self._play_seq_btn.setText("⏹  Stop")
            if self._current_index < 0:
                self._select_clip(0)
            if not self._preview.is_playing:
                self._preview.toggle_play_pause()

    def _stop_sequence(self):
        self._playing_sequence = False
        self._play_seq_btn.setText("▶  Play All")

    def _on_clip_ended(self):
        self._update_timeline_progress(1.0)
        if not self._playing_sequence:
            return
        next_idx = self._current_index + 1
        if next_idx < self._timeline.count():
            self._select_clip(next_idx)
            self._preview.toggle_play_pause()
        else:
            self._stop_sequence()

    # ------------------------------------------------------------------ export

    def _get_ordered_paths(self) -> list:
        return [
            self._timeline.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._timeline.count())
        ]

    def _export_sequence(self):
        paths = self._get_ordered_paths()
        if not paths:
            QMessageBox.warning(self, "Nothing to export", "Add clips to the timeline first.")
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Export stitched video", "chaos_sequence.mp4", "MP4 video (*.mp4)"
        )
        if not out_path:
            return

        self._export_btn.setEnabled(False)
        self._export_btn.setText("Exporting…")

        self._export_worker = _ExportWorker(paths, out_path)
        self._export_worker.finished.connect(self._on_export_done)
        self._export_worker.start()

    def _on_export_done(self, success: bool, msg: str):
        self._export_btn.setEnabled(True)
        self._export_btn.setText("Export as one video…")
        if success:
            QMessageBox.information(self, "Export complete", f"Saved to:\n{msg}")
        else:
            QMessageBox.critical(self, "Export failed", f"FFmpeg error:\n{msg}")
