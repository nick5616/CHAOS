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


# (details key, label) for the killfeed icons a kill can carry, in killfeed order
KILL_FLAGS: list[tuple[str, str]] = [
    ("attackerBlind", "While blind"),
    ("inAir",         "In the air"),
    ("noScope",       "No-scope"),
    ("throughSmoke",  "Through smoke"),
    ("wallbang",      "Wallbang"),
    ("isHeadshot",    "Headshot"),
]


def kill_flags(details: dict) -> list[str]:
    return [label for key, label in KILL_FLAGS if details.get(key)]


def _overlay_text(ev: dict) -> str:
    """Short overlay string shown at the moment an event occurs during playback."""
    t = ev.get("type", "")
    d = ev.get("details", {})
    if t == "kill":
        victim = d.get("victim", "?")
        parts = [f"ELIMINATED  {victim.upper()}"] + [f.upper() for f in kill_flags(d)]
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


def _marker_tooltip(ev: dict, at_s: float) -> str:
    """Tooltip shown when hovering an event marker on the timeline; `at_s` is
    the event's time within the clip."""
    t = ev.get("type", "")
    ts = at_s
    d = ev.get("details", {})
    if t == "kill":
        victim = d.get("victim", "?")
        killer = d.get("inferred_player") or d.get("detected_player")
        flags = kill_flags(d)
        info = f"{killer} killed {victim}" if killer else f"Kill → {victim}"
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
    Markers that would overlap stack upward in lanes above the groove, and the
    widget grows to fit them. Hover over a marker to see event details.
    Click/drag to seek. Emits seek_pressed, seek_moved(int) while dragging and
    seek_released(int) instead of QSlider signals.
    """

    seek_pressed = pyqtSignal()
    seek_moved = pyqtSignal(int)      # position in ms while dragging
    seek_released = pyqtSignal(int)   # new position in ms

    _BASE_H = 28
    _PAD_X = 9          # scrubber handle radius + 2, so it isn't clipped at either end
    _MARKER_R = 5
    _LANE_H = 12        # vertical step between stacked markers

    def __init__(self):
        super().__init__()
        self._range_max = 0
        self._position = 0
        self._events: list[tuple[int, dict]] = []   # (offset_ms, event_dict)
        self._markers: list[tuple[int, int, dict, int]] = []  # (x, lane, event, offset_ms), from _relayout
        self._dragging = False
        self._enabled = False
        self.setMouseTracking(True)
        self.setFixedHeight(self._BASE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── public API matching QSlider's interface ────────────────────────────────

    def setRange(self, _min: int, max_val: int):
        self._range_max = max_val
        self._relayout()

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
        self._relayout()

    def clear_events(self):
        self._events = []
        self._relayout()

    # ── layout ────────────────────────────────────────────────────────────────

    def _ms_to_x(self, ms: int) -> int:
        span = max(1, self.width() - 2 * self._PAD_X)
        return self._PAD_X + int(span * ms / self._range_max) if self._range_max else self._PAD_X

    def _groove_cy(self) -> int:
        return self.height() - self._BASE_H // 2

    def _relayout(self):
        """Assign each marker the lowest lane where it doesn't overlap a
        neighbour, then size the widget to fit the tallest stack."""
        self._markers = []
        if self._range_max > 0:
            gap = 2 * self._MARKER_R + 3
            lane_last_x: list[int] = []
            placed = sorted(((self._ms_to_x(ms), ev, ms) for ms, ev in self._events
                             if 0 <= ms <= self._range_max), key=lambda m: m[0])
            for x, ev, ms in placed:
                lane = next((i for i, last in enumerate(lane_last_x) if x - last >= gap), None)
                if lane is None:
                    lane = len(lane_last_x)
                    lane_last_x.append(x)
                lane_last_x[lane] = x
                self._markers.append((x, lane, ev, ms))
        lanes = 1 + max((m[1] for m in self._markers), default=0)
        self.setFixedHeight(self._BASE_H + (lanes - 1) * self._LANE_H)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self._relayout()   # marker x positions, and so the stacking, depend on width

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        groove_h = 4
        cy = self._groove_cy()
        groove_y = cy - groove_h // 2
        left, right = self._PAD_X, w - self._PAD_X

        # Background groove
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1a1d23")))
        painter.drawRoundedRect(left, groove_y, right - left, groove_h, 2, 2)

        if not self._enabled or self._range_max == 0:
            return

        # Progress fill
        hx = self._ms_to_x(self._position)
        painter.setBrush(QBrush(QColor("#e8963c")))
        painter.drawRoundedRect(left, groove_y, hx - left, groove_h, 2, 2)

        # Event markers — distinct shape per event type, stacked upward when they'd overlap
        r = self._MARKER_R
        for x, lane, ev, _ms in self._markers:
            my = cy - lane * self._LANE_H
            if lane:
                # Thin stem back down to the groove so a stacked marker still reads as "at this time"
                painter.setPen(QPen(QColor("#3a3d45"), 1))
                painter.drawLine(x, my + r, x, cy)
            ev_type = ev.get("type", "")
            color_hex = _EVENT_COLORS.get(ev_type, ("#6b7280", ""))[0]
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(QPen(QColor("#0a0c10"), 1.5))
            self._draw_marker(painter, ev_type, x, my, r)

        # Scrubber handle — white so it's distinct from milestone colors
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(hx - 7, cy - 7, 14, 14)
        # Inner dot
        painter.setBrush(QBrush(QColor("#9ca3af")))
        painter.drawEllipse(hx - 3, cy - 3, 6, 6)

    @staticmethod
    def _draw_marker(painter: QPainter, ev_type: str, x: int, cy: int, r: int):
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

    # ── mouse ─────────────────────────────────────────────────────────────────

    def _pos_to_ms(self, x: int) -> int:
        span = self.width() - 2 * self._PAD_X
        if span <= 0 or self._range_max == 0:
            return 0
        return int(max(0.0, min(1.0, (x - self._PAD_X) / span)) * self._range_max)

    def mousePressEvent(self, event):
        if not self._enabled:
            return
        self._dragging = True
        self._position = self._pos_to_ms(event.pos().x())
        self.seek_pressed.emit()
        self.seek_moved.emit(self._position)
        self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._position = self._pos_to_ms(event.pos().x())
            self.seek_moved.emit(self._position)
            self.update()
            return

        # Tooltip on hover near a marker
        pos = event.pos()
        cy = self._groove_cy()
        for x, lane, ev, ms in self._markers:
            if abs(pos.x() - x) <= 7 and abs(pos.y() - (cy - lane * self._LANE_H)) <= 7:
                QToolTip.showText(event.globalPosition().toPoint(), _marker_tooltip(ev, ms / 1000), self)
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

    _PLAY_TEXT = "▶  Play"
    _PAUSE_TEXT = "❚❚  Pause"

    def __init__(self):
        super().__init__()
        self.clip_path = None
        self._seeking = False
        self._first_frame: QPixmap | None = None
        self._raw_events: list[dict] = []
        self._clip_start_s: float = 0.0
        self._triggered_events: set[int] = set()
        self._last_position_ms: int = 0
        self._scrub_cap = None              # cv2 capture for showing frames while not playing
        self._pending_seek_ms: int | None = None   # where play() should start from
        self._scrub_target_ms: int | None = None
        self._scrub_timer = QTimer(singleShot=True)
        self._scrub_timer.setInterval(40)   # at most ~25 frame decodes/s while dragging
        self._scrub_timer.timeout.connect(self._show_scrub_frame)

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

        self.play_pause_btn = QPushButton(self._PLAY_TEXT)
        self.play_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Size in the stylesheet: QSS min/max sizes override setFixedSize
        self.play_pause_btn.setStyleSheet(
            "QPushButton { background: #1a1d23; border: 1px solid #2a2d35;"
            "border-radius: 6px; color: #e8963c; font-size: 13px;"
            "font-weight: bold; padding: 0 10px;"
            "min-width: 84px; max-width: 84px; min-height: 34px; max-height: 34px; }"
            "QPushButton:hover { background: #22262e; border-color: #e8963c; }"
            "QPushButton:disabled { color: #3a3d45; border-color: #1a1d23; }"
        )
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        # Bottom-aligned: the timeline grows upward when markers stack
        ctrl.addWidget(self.play_pause_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._timeline = EventTimelineWidget()
        self._timeline.seek_pressed.connect(self._on_seek_pressed)
        self._timeline.seek_moved.connect(self._on_seek_moved)
        self._timeline.seek_released.connect(self._on_seek_released)
        self._timeline.setEnabled(False)
        ctrl.addWidget(self._timeline, 1, Qt.AlignmentFlag.AlignBottom)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet(
            "color: #6b7280; font-size: 11px; font-family: monospace;"
        )
        self.time_label.setMinimumWidth(88)
        self.time_label.setFixedHeight(36)
        ctrl.addWidget(self.time_label, 0, Qt.AlignmentFlag.AlignBottom)

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
        self._pending_seek_ms = None
        self._open_scrub_cap(clip_path)

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
                pending, self._pending_seek_ms = self._pending_seek_ms, None
                self.player.play()
                if pending is not None:
                    # After play(): from a stopped player, a position set
                    # beforehand isn't reliably kept.
                    self.player.setPosition(pending)

    def clear(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.clip_path = None
        self._first_frame = None
        self._pending_seek_ms = None
        self._scrub_timer.stop()
        self._release_scrub_cap()
        self._raw_events = []
        self._triggered_events = set()
        self._overlay_timer.stop()
        self._overlay.hide()
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setText(self._PLAY_TEXT)
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
            return self._to_pixmap(frame) if ret else None
        except Exception:
            return None

    @staticmethod
    def _to_pixmap(frame) -> QPixmap:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]
        img = QImage(frame_rgb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img)

    # ── scrubbing while not playing ───────────────────────────────────────────
    # QMediaPlayer doesn't paint a new frame when a stopped (never played, or
    # ended) player is seeked, so while not playing the frame at the seek
    # position is decoded with OpenCV and shown in the still-image label.

    def _open_scrub_cap(self, path: str):
        self._release_scrub_cap()
        cap = cv2.VideoCapture(path)
        self._scrub_cap = cap if cap.isOpened() else None

    def _release_scrub_cap(self):
        if self._scrub_cap is not None:
            self._scrub_cap.release()
            self._scrub_cap = None

    def _show_scrub_frame(self):
        if self._scrub_target_ms is None or self._scrub_cap is None:
            return
        self._scrub_cap.set(cv2.CAP_PROP_POS_MSEC, self._scrub_target_ms)
        ok, frame = self._scrub_cap.read()
        if not ok:
            return
        self._first_frame = self._to_pixmap(frame)   # what resizes re-render
        self._render_first_frame()
        self._display_stack.setCurrentIndex(0)

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

    def _on_seek_moved(self, pos_ms: int):
        if self.is_playing:
            return
        self._update_time(pos_ms)
        self._scrub_target_ms = pos_ms
        if not self._scrub_timer.isActive():
            self._scrub_timer.start()

    def _on_seek_released(self, pos_ms: int):
        self._seeking = False
        if self.is_playing:
            self.player.setPosition(pos_ms)
            return
        self._scrub_timer.stop()
        self._scrub_target_ms = pos_ms
        self._show_scrub_frame()
        self._pending_seek_ms = pos_ms
        self._last_position_ms = pos_ms
        self._triggered_events = set()
        self.player.setPosition(pos_ms)
        self._timeline.setValue(pos_ms)
        self._update_time(pos_ms)

    def _on_position_changed(self, pos_ms: int):
        self._timeline.setValue(pos_ms)
        self._update_time(pos_ms)
        if self.is_playing:
            self._check_events_at_position(pos_ms)

    def _on_duration_changed(self, dur_ms: int):
        self._timeline.setRange(0, max(0, dur_ms))

    def _on_playback_state_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_pause_btn.setText(self._PAUSE_TEXT if playing else self._PLAY_TEXT)

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
