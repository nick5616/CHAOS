"""
Results view — shows ranked highlight clips after a pipeline run.
"""

import os
import json
import glob
import platform
import subprocess

import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QTextEdit,
)
from PyQt6.QtCore import Qt

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.widgets.clip_preview import ClipPreviewWidget


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


# (display label, foreground, background) per tag
_TAG_STYLE: dict[str, tuple[str, str, str]] = {
    "multi-kill":    ("MULTI-KILL",    "#c084fc", "#2e1065"),
    "headshot":      ("HEADSHOT",      "#f59e0b", "#431407"),
    "smoke_kill":    ("SMOKE KILL",    "#67e8f9", "#0c4a6e"),
    "team_hype":     ("TEAM HYPE",     "#4ade80", "#052e16"),
    "enemy_rage":    ("ENEMY RAGE",    "#f87171", "#450a0a"),
    "loud_reaction": ("LOUD REACTION", "#60a5fa", "#0c1a4e"),
}


def _make_chip(tag: str) -> QLabel:
    label, fg, bg = _TAG_STYLE.get(
        tag, (tag.upper().replace("_", " "), "#c8ccd4", "#1a1d23")
    )
    chip = QLabel(label)
    chip.setStyleSheet(
        f"color: {fg}; background: {bg}; border: 1px solid {fg}50;"
        f"border-radius: 3px; padding: 2px 8px;"
        f"font-size: 10px; font-weight: bold; letter-spacing: 1px;"
    )
    return chip


class ResultsView(QWidget):
    """Ranked clips list with chip tags, detail panel, and preview."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.clips_data = []
        self._input_bytes = 0
        self._build_ui()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #4b5563; font-size: 10px; font-weight: bold;"
            "letter-spacing: 2px; background: transparent;"
        )
        return lbl

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._count_label = QLabel("No clips yet — run the pipeline to find highlights")
        self._count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        toolbar.addWidget(self._count_label)

        self._ratio_label = QLabel("")
        self._ratio_label.setStyleSheet(
            "color: #4ade80; font-size: 11px; font-weight: bold;"
            "background: #0d2318; border: 1px solid #166534;"
            "border-radius: 3px; padding: 2px 8px;"
        )
        self._ratio_label.setVisible(False)
        toolbar.addWidget(self._ratio_label)

        toolbar.addStretch()

        refresh_btn = QPushButton("↺  REFRESH")
        refresh_btn.setStyleSheet("font-size: 11px; letter-spacing: 1px; padding: 5px 14px;")
        refresh_btn.clicked.connect(self.load_results)
        toolbar.addWidget(refresh_btn)

        open_btn = QPushButton("FOLDER  ↗")
        open_btn.setStyleSheet("font-size: 11px; letter-spacing: 1px; padding: 5px 14px;")
        open_btn.clicked.connect(self._open_folder)
        toolbar.addWidget(open_btn)

        root.addLayout(toolbar)

        # Hairline divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #1e2128;")
        divider.setMaximumHeight(1)
        root.addWidget(divider)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(self._section_label("HIGHLIGHTS"))

        self._clips_list = QListWidget()
        self._clips_list.setStyleSheet(
            "QListWidget { border: 1px solid #1e2128; background: #0a0c10; border-radius: 4px; }"
            "QListWidget::item { padding: 9px 12px; border-bottom: 1px solid #131519; }"
            "QListWidget::item:selected { background: #1c2028; color: #e8963c; border-left: 2px solid #e8963c; padding-left: 10px; }"
            "QListWidget::item:hover:!selected { background: #131519; }"
        )
        self._clips_list.itemSelectionChanged.connect(self._on_selected)
        left_layout.addWidget(self._clips_list, 3)

        left_layout.addSpacing(4)
        left_layout.addWidget(self._section_label("DETAILS"))

        # Chip row for tags
        self._chip_row = QHBoxLayout()
        self._chip_row.setSpacing(5)
        self._chip_row.setContentsMargins(0, 2, 0, 2)
        chip_container = QWidget()
        chip_container.setLayout(self._chip_row)
        chip_container.setStyleSheet("background: transparent;")
        chip_container.setFixedHeight(28)
        left_layout.addWidget(chip_container)

        # Details text (rich text, scrollable)
        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setStyleSheet(
            "QTextEdit { background: #0a0c10; border: 1px solid #1e2128;"
            "border-radius: 4px; color: #9ca3af; padding: 6px 8px; }"
        )
        left_layout.addWidget(self._details_text, 2)

        splitter.addWidget(left)

        # ── Right panel — preview ─────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(6)

        preview_hdr = QHBoxLayout()
        preview_hdr.setContentsMargins(0, 0, 0, 0)
        preview_hdr.setSpacing(8)
        preview_hdr.addWidget(self._section_label("PREVIEW"))
        self._preview_name_lbl = QLabel("")
        self._preview_name_lbl.setStyleSheet(
            "color: #6b7280; font-size: 10px; background: transparent;"
        )
        preview_hdr.addWidget(self._preview_name_lbl, 1)
        right_layout.addLayout(preview_hdr)

        self._preview = ClipPreviewWidget()
        right_layout.addWidget(self._preview, 1)

        splitter.addWidget(right)
        splitter.setSizes([380, 620])
        root.addWidget(splitter, 1)

    # ── load ──────────────────────────────────────────────────────────────────

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
            tag_display = (
                "  ·  " + "  ·  ".join(
                    _TAG_STYLE.get(t, (t.upper().replace("_", " "), "", ""))[0]
                    for t in tags
                )
                if tags else ""
            )
            text = f"#{i+1:02d}  ·  {score} pts{tag_display}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, clip)
            self._clips_list.addItem(item)

        n = len(self.clips_data)
        self._count_label.setText(f"{n} highlight{'s' if n != 1 else ''} found")

        # Auto-select the first clip
        self._clips_list.setCurrentRow(0)

    # ── selection ─────────────────────────────────────────────────────────────

    def _on_selected(self):
        item = self._clips_list.currentItem()
        if not item:
            self._clear_details()
            return
        clip = item.data(Qt.ItemDataRole.UserRole)
        file_start_s, actual_dur_s = self._try_preview(clip)
        self._update_details(clip, file_start_s, actual_dur_s)

    def _clear_details(self):
        while self._chip_row.count():
            w = self._chip_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._details_text.clear()

    def _update_details(self, clip: dict, file_start_s: float = 0.0, actual_dur_s: float = 0.0):
        self._clear_details()

        # Chips
        for tag in clip.get("tags", []):
            self._chip_row.addWidget(_make_chip(tag))
        self._chip_row.addStretch()

        # Text details (rich HTML)
        source = os.path.basename(clip.get("source_video", "Unknown"))
        events = clip.get("events_in_window", [])

        dur_display = f"{actual_dur_s:.1f}s" if actual_dur_s > 0 else "—"

        dim = "#4b5563"
        acc = "#e8963c"
        muted = "#6b7280"

        lines = [
            f"<span style='color:{muted}'>SCORE</span>&nbsp;&nbsp;"
            f"<span style='color:{acc}; font-weight:bold'>{clip.get('score', 0)}</span>"
            f"&nbsp;&nbsp;<span style='color:{dim}'>·</span>&nbsp;&nbsp;"
            f"<span style='color:{muted}'>DURATION</span>&nbsp;&nbsp;"
            f"<span style='color:#c8ccd4'>{dur_display}</span>",

            f"<span style='color:{muted}'>SOURCE</span>&nbsp;&nbsp;"
            f"<span style='color:#6b7280'>{source}</span>",
        ]

        kills  = [e for e in events if e.get("type") == "kill"]
        voices = [e for e in events if e.get("type") == "voice"]
        chats  = [e for e in events if e.get("type") == "chat"]
        spikes = [e for e in events if e.get("type") == "audio_spike"]

        event_lines = []
        for ev in kills:
            d = ev.get("details", {})
            victim = d.get("victim", "?")
            flags = []
            if d.get("isHeadshot"):    flags.append("HS")
            if d.get("throughSmoke"):  flags.append("SMOKE")
            flag_str = f"&nbsp;<span style='color:{muted}'>[{' · '.join(flags)}]</span>" if flags else ""
            ts = max(0.0, ev.get("timestamp_seconds", 0) - file_start_s)
            event_lines.append(
                f"&nbsp;&nbsp;<span style='color:{acc}'>KILL</span>"
                f"&nbsp;&nbsp;{victim}{flag_str}"
                f"&nbsp;&nbsp;<span style='color:{dim}'>@ {ts:.1f}s</span>"
            )
        for ev in voices:
            txt = ev.get("details", {}).get("text", "").strip()
            if txt:
                ts = max(0.0, ev.get("timestamp_seconds", 0) - file_start_s)
                event_lines.append(
                    f"&nbsp;&nbsp;<span style='color:#4ade80'>◈ VOICE</span>"
                    f"&nbsp;&nbsp;\"{txt}\""
                    f"&nbsp;&nbsp;<span style='color:{dim}'>@ {ts:.1f}s</span>"
                )
        for ev in chats:
            txt = ev.get("details", {}).get("text", "").strip()
            if txt:
                ts = max(0.0, ev.get("timestamp_seconds", 0) - file_start_s)
                event_lines.append(
                    f"&nbsp;&nbsp;<span style='color:#f87171'>◈ CHAT</span>"
                    f"&nbsp;&nbsp;\"{txt}\""
                    f"&nbsp;&nbsp;<span style='color:{dim}'>@ {ts:.1f}s</span>"
                )
        for ev in spikes:
            intensity = ev.get("details", {}).get("intensity", 0)
            ts = max(0.0, ev.get("timestamp_seconds", 0) - file_start_s)
            event_lines.append(
                f"&nbsp;&nbsp;<span style='color:#60a5fa'>◉ CROWD</span>"
                f"&nbsp;&nbsp;{intensity:.0%} intensity"
                f"&nbsp;&nbsp;<span style='color:{dim}'>@ {ts:.1f}s</span>"
            )

        if event_lines:
            lines.append("")
            lines.extend(event_lines[:8])
            if len(events) > 8:
                lines.append(
                    f"&nbsp;&nbsp;<span style='color:{dim}'>… and {len(events) - 8} more events</span>"
                )

        self._details_text.setHtml(
            "<div style='font-size:12px; line-height:1.6;'>"
            + "<br>".join(lines)
            + "</div>"
        )

    def _try_preview(self, clip_data: dict) -> tuple:
        """Load clip into the preview widget. Returns (file_start_s, actual_dur_s)."""
        try:
            config = self.config_manager.load_config()
            clips_folder = self.config_manager.resolve_path(
                config.get("final_clips_folder", "./final_clips")
            )

            pre_buffer_s = float(config.get("clip_pre_buffer_seconds", 7))
            clip_start = float(clip_data.get("clip_start", 0))
            file_start_s = max(0.0, clip_start - pre_buffer_s)

            # The pipeline records the exact output filename on each highlight
            # (clip_filename) at clip-cut time. That's the only reliable way
            # to find "this" clip's file — clips are cut in streaming order as
            # each video finishes analysis, not in final rank order, so
            # reconstructing a filename from this entry's position in the
            # (score-sorted) list can resolve to a completely different clip.
            candidates = []
            clip_filename = clip_data.get("clip_filename")
            if clip_filename:
                candidates.append(os.path.join(clips_folder, clip_filename))
            else:
                # Older results predating clip_filename tracking — best effort only.
                idx = self.clips_data.index(clip_data) + 1
                score = clip_data.get("score", 0)
                for pattern in [
                    os.path.join(clips_folder, f"{idx}_{score}_*.mp4"),
                    os.path.join(clips_folder, f"{idx}_*.mp4"),
                ]:
                    candidates.extend(glob.glob(pattern))

            for path in candidates:
                if os.path.exists(path) and self._preview.load_clip(path):
                    self._preview.set_events(
                        clip_data.get("events_in_window", []),
                        file_start_s,
                    )
                    actual_dur_s = self._get_clip_duration(path)
                    self._preview_name_lbl.setText(os.path.basename(path))
                    return file_start_s, actual_dur_s

            self._preview.show_message("Clip file not found")
            self._preview_name_lbl.setText("")
            return 0.0, 0.0
        except Exception as e:
            self._preview.show_message(f"Preview error: {e}")
            self._preview_name_lbl.setText("")
            return 0.0, 0.0

    def _get_clip_duration(self, path: str) -> float:
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return 0.0
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            return frames / fps if fps > 0 else 0.0
        except Exception:
            return 0.0

    # ── folder ────────────────────────────────────────────────────────────────

    def _open_folder(self):
        try:
            config = self.config_manager.load_config()
            folder = self.config_manager.resolve_path(
                config.get("final_clips_folder", "./final_clips")
            )
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
