"""
Clip preview widget — QMediaPlayer-based playback with audio support.
Shows the first frame as a static image until the user presses play.
Includes an EventTimelineWidget with per-event markers and playback overlays.
"""

import os
import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QStackedWidget, QGraphicsOpacityEffect, QToolTip,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QPropertyAnimation
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


# (foreground_hex, dark_bg_hex) per event type — used for marker dots
_EVENT_COLORS: dict[str, tuple[str, str]] = {
    "kill":        ("#e8963c", "#431407"),
    "audio_spike": ("#3b82f6", "#0c1a4e"),
    "voice":       ("#4ade80", "#052e16"),
    "chat":        ("#f87171", "#450a0a"),
}


def _overlay_text(ev: dict) -> str:
    """Short overlay string shown at the moment an event occurs during playback."""
    t = ev.get("type", "")
    d = ev.get("details", {})
    if t == "kill":
        victim = d.get("victim", "?")
        parts = [f"ELIMINATED  {victim.upper()}"]
        if d.get("isHeadshot"):   parts.append("HEADSHOT")
        if d.get("throughSmoke"): parts.append("THROUGH SMOKE")
        return "  ·  ".join(parts)
    if t == "voice":
        txt = d.get("text", "").strip()
        return f'"{txt}"' if txt else "VOICE"
    if t == "chat":
        txt = d.get("text", "").strip()
        return f'CHAT: "{txt}"' if txt else "CHAT"
    if t == "audio_spike":
        return "CROWD REACTION"
    return t.upper()


def _marker_tooltip(ev: dict) -> str:
    """Tooltip shown when hovering an event marker on the timeline."""
    t = ev.get("type", "")
    ts = ev.get("timestamp_seconds", 0)
    d = ev.get("details", {})
    if t == "kill":
        victim = d.get("victim", "?")
        flags = []
        if d.get("isHeadshot"):   flags.append("Headshot")
        if d.get("throughSmoke"): flags.append("Through smoke")
        info = f"Kill → {victim}"
        if flags:
            info += "\n" + " · ".join(flags)
    elif t == "voice":
        txt = d.get("text", "").strip()
        info = f'"{txt}"' if txt else "Voice segment"
    elif t == "chat":
        txt = d.get("text", "").strip()
        info = f'Chat: "{txt}"' if txt else "Chat message"
    elif t == "audio_spike":
        pct = d.get("intensity", 0)
        info = f"Loud reaction  {pct:.0%}"
    else:
        info = t
    return f"{info}\n@ {ts:.1f}s"


# ── EventTimelineWidget ────────────────────────────────────────────────────────


class EventTimelineWidget(QWidget):
    """
    Custom seek bar that paints colored event markers on the timeline.
    Hover over a marker to see event details. Click/drag to seek.
    Emits seek_pressed and seek_released(int) instead of QSlider signals.
    """

    seek_pressed = pyqtSignal()
    seek_released = pyqtSignal(int)   # new position in ms

    def __init__(self):
        super().__init__()
        self._range_max = 0
        self._position = 0
        self._events: list[tuple[int, dict]] = []   # (offset_ms, event_dict)
        self._dragging = False
        self._enabled = False
        self.setMouseTracking(True)
        self.setMinimumHeight(28)
        self.setMaximumHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── public API matching QSlider's interface ────────────────────────────────

    def setRange(self, _min: int, max_val: int):
        self._range_max = max_val
        self.update()

    def setValue(self, val: int):
        if not self._dragging:
            self._position = max(0, min(val, self._range_max))
            self.update()

    def value(self) -> int:
        return self._position

    def setEnabled(self, enabled: bool):
        self._enabled = enabled
        self.update()

    def set_events(self, events: list, clip_start_s: float):
        self._events = []
        for ev in events:
            ts = ev.get("timestamp_seconds", 0)
            offset_ms = int((ts - clip_start_s) * 1000)
            self._events.append((offset_ms, ev))
        self.update()

    def clear_events(self):
        self._events = []
        self.update()

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        groove_h = 4
        groove_y = (h - groove_h) // 2

        # Background groove
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1a1d23")))
        painter.drawRoundedRect(0, groove_y, w, groove_h, 2, 2)

        if not self._enabled or self._range_max == 0:
            return

        # Progress fill
        prog_w = int(w * self._position / self._range_max)
        painter.setBrush(QBrush(QColor("#e8963c")))
        painter.drawRoundedRect(0, groove_y, prog_w, groove_h, 2, 2)

        # Event markers — distinct shape per event type
        cy = h // 2
        for offset_ms, ev in self._events:
            if not (0 <= offset_ms <= self._range_max):
                continue
            x = int(w * offset_ms / self._range_max)
            ev_type = ev.get("type", "")
            color_hex = _EVENT_COLORS.get(ev_type, ("#6b7280", ""))[0]
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(QPen(QColor("#0a0c10"), 1.5))
            r = 5

            if ev_type == "kill":
                # Diamond
                path = QPainterPath()
                path.moveTo(x, cy - r)
                path.lineTo(x + r, cy)
                path.lineTo(x, cy + r)
                path.lineTo(x - r, cy)
                path.closeSubpath()
                painter.drawPath(path)
            elif ev_type == "audio_spike":
                # Triangle pointing up
                path = QPainterPath()
                path.moveTo(x, cy - r)
                path.lineTo(x + r, cy + r)
                path.lineTo(x - r, cy + r)
                path.closeSubpath()
                painter.drawPath(path)
            elif ev_type == "chat":
                # Square
                painter.drawRect(x - r + 1, cy - r + 1, (r - 1) * 2, (r - 1) * 2)
            else:
                # Circle (voice, default)
                painter.drawEllipse(x - r, cy - r, r * 2, r * 2)

        # Scrubber handle — white so it's distinct from milestone colors
        hx = int(w * self._position / self._range_max)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(hx - 7, (h - 14) // 2, 14, 14)
        # Inner dot
        painter.setBrush(QBrush(QColor("#9ca3af")))
        painter.drawEllipse(hx - 3, (h - 6) // 2, 6, 6)

    # ── mouse ─────────────────────────────────────────────────────────────────

    def _pos_to_ms(self, x: int) -> int:
        if self.width() == 0 or self._range_max == 0:
            return 0
        return int(max(0.0, min(1.0, x / self.width())) * self._range_max)

    def mousePressEvent(self, event):
        if not self._enabled:
            return
        self._dragging = True
        self._position = self._pos_to_ms(event.pos().x())
        self.seek_pressed.emit()
        self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._position = self._pos_to_ms(event.pos().x())
            self.update()
            return

        # Tooltip on hover near a marker
        x = event.pos().x()
        if self._range_max > 0:
            for offset_ms, ev in self._events:
                mx = int(self.width() * offset_ms / self._range_max)
                if abs(x - mx) <= 8:
                    QToolTip.showText(
                        event.globalPosition().toPoint(),
                        _marker_tooltip(ev),
                        self,
                    )
                    return
            QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        if not self._dragging:
            return
        self._dragging = False
        self._position = self._pos_to_ms(event.pos().x())
        self.seek_released.emit(self._position)
        self.update()


# ── ClipPreviewWidget ──────────────────────────────────────────────────────────


class ClipPreviewWidget(QWidget):
    """Video + audio preview; shows first frame before play is pressed."""

    clip_ended = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.clip_path = None
        self._seeking = False
        self._first_frame: QPixmap | None = None
        self._raw_events: list[dict] = []
        self._clip_start_s: float = 0.0
        self._triggered_events: set[int] = set()
        self._last_position_ms: int = 0

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self._init_ui()

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_error)

    @property
    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # ── UI ────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Video display — stack switches between static thumbnail and live video
        self._display_stack = QStackedWidget()

        self.video_display = QLabel("No clip selected")
        self.video_display.setMinimumSize(400, 225)
        self.video_display.setStyleSheet(
            "border: none; background-color: #070809; color: #3a3d45;"
        )
        self.video_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._display_stack.addWidget(self.video_display)

        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumSize(400, 225)
        self._video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.player.setVideoOutput(self._video_widget)
        self._display_stack.addWidget(self._video_widget)

        layout.addWidget(self._display_stack, 1)

        # Floating event overlay (child of this widget, positioned over video)
        self._overlay = QLabel("", self)
        self._overlay.setStyleSheet(
            "color: #e8963c; background: rgba(7, 8, 9, 210);"
            "border: 1px solid #e8963c55; border-radius: 4px;"
            "padding: 7px 16px; font-size: 13px; font-weight: bold; letter-spacing: 1px;"
        )
        self._overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay.setWordWrap(False)
        self._overlay.hide()

        self._overlay_effect = QGraphicsOpacityEffect(self._overlay)
        self._overlay.setGraphicsEffect(self._overlay_effect)

        self._fade_in = QPropertyAnimation(self._overlay_effect, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self._overlay_effect, b"opacity")
        self._fade_out.setDuration(500)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self._overlay.hide)

        self._overlay_timer = QTimer(singleShot=True)
        self._overlay_timer.timeout.connect(self._begin_fade_out)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        ctrl.setContentsMargins(0, 0, 0, 0)

        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setFixedSize(32, 32)
        self.play_pause_btn.setStyleSheet(
            "QPushButton { background: #1a1d23; border: 1px solid #2a2d35;"
            "border-radius: 16px; color: #e8963c; font-size: 14px;"
            "font-weight: bold; padding: 0; min-width: 0; }"
            "QPushButton:hover { background: #22262e; border-color: #e8963c; }"
            "QPushButton:disabled { color: #3a3d45; border-color: #1a1d23; }"
        )
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        ctrl.addWidget(self.play_pause_btn)

        self._timeline = EventTimelineWidget()
        self._timeline.seek_pressed.connect(self._on_seek_pressed)
        self._timeline.seek_released.connect(self._on_seek_released)
        self._timeline.setEnabled(False)
        ctrl.addWidget(self._timeline, 1)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet(
            "color: #6b7280; font-size: 11px; font-family: monospace;"
        )
        self.time_label.setMinimumWidth(88)
        ctrl.addWidget(self.time_label)

        layout.addLayout(ctrl)

    # ── public API ────────────────────────────────────────────────────────────

    def load_clip(self, clip_path: str) -> bool:
        if not os.path.exists(clip_path):
            self.show_message("Clip file not found")
            return False

        self.player.stop()
        self.clip_path = clip_path
        self._triggered_events = set()
        self._last_position_ms = 0
        self._raw_events = []
        self._clip_start_s = 0.0

        self._first_frame = self._extract_first_frame(clip_path)
        if self._first_frame:
            self._render_first_frame()
        else:
            self.video_display.setText("")
        self._display_stack.setCurrentIndex(0)

        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(clip_path)))
        self.play_pause_btn.setEnabled(True)
        self._timeline.setEnabled(True)
        return True

    def set_events(self, events: list, clip_start_s: float):
        """Register events for timeline markers and playback overlays."""
        self._raw_events = events
        self._clip_start_s = clip_start_s
        self._triggered_events = set()
        self._timeline.set_events(events, clip_start_s)

    def show_message(self, text: str):
        self._first_frame = None
        self.video_display.setPixmap(QPixmap())
        self.video_display.setText(text)
        self._display_stack.setCurrentIndex(0)

    def toggle_play_pause(self):
        if not self.player.source().isEmpty():
            if self.is_playing:
                self.player.pause()
            else:
                self._display_stack.setCurrentIndex(1)
                self.player.play()

    def clear(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.clip_path = None
        self._first_frame = None
        self._raw_events = []
        self._triggered_events = set()
        self._overlay_timer.stop()
        self._overlay.hide()
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setText("▶")
        self._timeline.setRange(0, 0)
        self._timeline.setEnabled(False)
        self._timeline.clear_events()
        self.time_label.setText("0:00 / 0:00")
        self.show_message("No clip selected")

    # ── overlay ───────────────────────────────────────────────────────────────

    def _show_overlay(self, text: str):
        self._overlay_timer.stop()
        self._fade_out.stop()
        self._overlay.setText(text)
        self._overlay.adjustSize()
        self._reposition_overlay()
        self._overlay.show()
        self._fade_in.start()
        self._overlay_timer.start(2800)

    def _begin_fade_out(self):
        self._fade_in.stop()
        self._fade_out.start()

    def _reposition_overlay(self):
        r = self._display_stack.geometry()
        if r.width() < 10:
            return
        ow = max(self._overlay.sizeHint().width() + 32, 200)
        oh = self._overlay.sizeHint().height() + 14
        ox = r.left() + (r.width() - ow) // 2
        oy = r.bottom() - oh - 36
        self._overlay.setGeometry(ox, oy, ow, oh)

    # ── event trigger during playback ─────────────────────────────────────────

    def _check_events_at_position(self, pos_ms: int):
        # Reset triggered set if user scrubbed backward significantly
        if self._last_position_ms - pos_ms > 1000:
            self._triggered_events = set()
        self._last_position_ms = pos_ms

        for idx, ev in enumerate(self._raw_events):
            if idx in self._triggered_events:
                continue
            offset_ms = int((ev.get("timestamp_seconds", 0) - self._clip_start_s) * 1000)
            # Fire overlay when playback head enters a 200ms window after the event
            if 0 <= (pos_ms - offset_ms) < 200:
                self._triggered_events.add(idx)
                self._show_overlay(_overlay_text(ev))
                break

    # ── first frame ───────────────────────────────────────────────────────────

    def _extract_first_frame(self, path: str) -> "QPixmap | None":
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame_rgb.shape[:2]
            img = QImage(frame_rgb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(img)
        except Exception:
            return None

    def _render_first_frame(self):
        if not self._first_frame:
            return
        size = self.video_display.size()
        if size.width() < 2 or size.height() < 2:
            return
        scaled = self._first_frame.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_display.setPixmap(scaled)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self, pos_ms: int):
        self._seeking = False
        self.player.setPosition(pos_ms)

    def _on_position_changed(self, pos_ms: int):
        self._timeline.setValue(pos_ms)
        self._update_time(pos_ms)
        if self.is_playing:
            self._check_events_at_position(pos_ms)

    def _on_duration_changed(self, dur_ms: int):
        self._timeline.setRange(0, max(0, dur_ms))

    def _on_playback_state_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_pause_btn.setText("⏸" if playing else "▶")

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.clip_ended.emit()

    def _on_error(self, _error, error_string: str):
        self.show_message(f"Playback error: {error_string}")

    def _update_time(self, pos_ms: int):
        dur_ms = self.player.duration()
        ps, ds = pos_ms / 1000, dur_ms / 1000
        self.time_label.setText(
            f"{int(ps // 60)}:{int(ps % 60):02d} / "
            f"{int(ds // 60)}:{int(ds % 60):02d}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._display_stack.currentIndex() == 0 and self._first_frame:
            self._render_first_frame()
        if self._overlay.isVisible():
            self._reposition_overlay()
