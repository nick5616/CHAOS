"""
Results view — shows ranked highlight clips after a pipeline run.
"""

import os
import json
import glob
import platform
import subprocess


def _fmt_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1e9:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f} MB"
    if n >= 1_000:
        return f"{n / 1e3:.1f} KB"
    return f"{n} B"


def _folder_mp4_size(folder: str) -> int:
    total = 0
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(".mp4"):
                total += entry.stat().st_size
    except OSError:
        pass
    return total
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QTextEdit, QGroupBox
)
from PyQt6.QtCore import Qt

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.widgets.clip_preview import ClipPreviewWidget


class ResultsView(QWidget):
    """Ranked clips list with detail panel and preview."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.clips_data = []
        self._input_bytes = 0
        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        # Toolbar
        toolbar = QHBoxLayout()
        self._count_label = QLabel("No clips yet — run the pipeline to find highlights")
        self._count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        toolbar.addWidget(self._count_label)

        self._ratio_label = QLabel("")
        self._ratio_label.setStyleSheet(
            "color: #4ade80; font-size: 12px; font-weight: bold; "
            "background: #0d2318; border: 1px solid #166534; border-radius: 4px; padding: 2px 8px;"
        )
        self._ratio_label.setVisible(False)
        toolbar.addWidget(self._ratio_label)

        toolbar.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_results)
        toolbar.addWidget(refresh_btn)

        open_btn = QPushButton("Open folder")
        open_btn.clicked.connect(self._open_folder)
        toolbar.addWidget(open_btn)

        root.addLayout(toolbar)

        # Main splitter: clip list + details | preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — list + details
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        clips_box = QGroupBox("Highlights")
        clips_vbox = QVBoxLayout(clips_box)
        self._clips_list = QListWidget()
        self._clips_list.itemSelectionChanged.connect(self._on_selected)
        clips_vbox.addWidget(self._clips_list)
        left_layout.addWidget(clips_box, 3)

        details_box = QGroupBox("Details")
        details_vbox = QVBoxLayout(details_box)
        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        details_vbox.addWidget(self._details_text)
        left_layout.addWidget(details_box, 2)

        splitter.addWidget(left)

        # Right — preview
        preview_box = QGroupBox("Preview")
        preview_vbox = QVBoxLayout(preview_box)
        self._preview = ClipPreviewWidget()
        preview_vbox.addWidget(self._preview)
        splitter.addWidget(preview_box)

        splitter.setSizes([420, 580])
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------ load

    def set_input_size(self, bytes_: int):
        self._input_bytes = bytes_

    def load_results(self):
        try:
            config = self.config_manager.load_config()
            data_folder = config.get("data_folder", "./data")
            highlights_path = os.path.join(data_folder, "ordered_highlights.json")

            if os.path.exists(highlights_path):
                with open(highlights_path, "r") as f:
                    self.clips_data = json.load(f)
            else:
                self.clips_data = []

            self._populate_list()
            self._update_ratio(config)
        except Exception as e:
            self._count_label.setText(f"Error loading results: {e}")

    def _update_ratio(self, config: dict):
        if self._input_bytes <= 0:
            self._ratio_label.setVisible(False)
            return
        clips_folder = self.config_manager.resolve_path(
            config.get("final_clips_folder", "./final_clips")
        )
        out_bytes = _folder_mp4_size(clips_folder)
        if out_bytes <= 0:
            self._ratio_label.setVisible(False)
            return
        ratio = self._input_bytes / out_bytes
        self._ratio_label.setText(
            f"{ratio:.1f}× smaller  ({_fmt_size(self._input_bytes)} → {_fmt_size(out_bytes)})"
        )
        self._ratio_label.setVisible(True)

    def _populate_list(self):
        self._clips_list.clear()

        if not self.clips_data:
            self._count_label.setText("No highlights found — run the pipeline first")
            return

        for i, clip in enumerate(self.clips_data):
            score = clip.get("score", 0)
            tags = clip.get("tags", [])
            tag_str = "  ·  " + ", ".join(tags) if tags else ""
            text = f"#{i+1:02d}   score {score}{tag_str}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, clip)
            self._clips_list.addItem(item)

        self._count_label.setText(f"{len(self.clips_data)} highlight{'s' if len(self.clips_data) != 1 else ''} found")

    # ------------------------------------------------------------------ selection

    def _on_selected(self):
        item = self._clips_list.currentItem()
        if not item:
            self._details_text.clear()
            return

        clip = item.data(Qt.ItemDataRole.UserRole)
        start = clip.get("clip_start", 0)
        end = clip.get("clip_end", 0)
        duration = end - start

        lines = [
            f"Score:     {clip.get('score', 0)}",
            f"Start:     {start:.2f}s",
            f"End:       {end:.2f}s",
            f"Duration:  {duration:.2f}s",
            f"Source:    {os.path.basename(clip.get('source_video', 'Unknown'))}",
        ]
        if clip.get("tags"):
            lines.append(f"Tags:      {', '.join(clip['tags'])}")

        events = clip.get("events_in_window", [])
        if events:
            lines.append(f"\nEvents ({len(events)}):")
            for ev in events[:6]:
                lines.append(f"  {ev.get('type', '?')}  @  {ev.get('timestamp_seconds', 0):.2f}s")
            if len(events) > 6:
                lines.append(f"  … and {len(events) - 6} more")

        self._details_text.setPlainText("\n".join(lines))
        self._try_preview(clip)

    def _try_preview(self, clip_data):
        try:
            config = self.config_manager.load_config()
            clips_folder = self.config_manager.resolve_path(
                config.get("final_clips_folder", "./final_clips")
            )
            idx = self.clips_data.index(clip_data) + 1
            score = clip_data.get("score", 0)

            for pattern in [
                os.path.join(clips_folder, f"{idx}_{score}_*.mp4"),
                os.path.join(clips_folder, f"{idx}_*.mp4"),
            ]:
                matches = glob.glob(pattern)
                if matches and self._preview.load_clip(matches[0]):
                    return

            self._preview.show_message("Clip file not found")
        except Exception as e:
            self._preview.show_message(f"Preview error: {e}")

    # ------------------------------------------------------------------ folder

    def _open_folder(self):
        try:
            config = self.config_manager.load_config()
            folder = self.config_manager.resolve_path(config.get("final_clips_folder", "./final_clips"))
            if not os.path.exists(folder):
                self._count_label.setText(f"Folder not found: {folder}")
                return
            system = platform.system()
            if system == "Darwin":
                subprocess.run(["open", folder])
            elif system == "Windows":
                subprocess.run(["explorer", os.path.normpath(folder)])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            self._count_label.setText(f"Could not open folder: {e}")
