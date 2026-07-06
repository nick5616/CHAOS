"""
Clip preview widget — QMediaPlayer-based playback with audio support.
Shows the first frame as a static image until the user presses play.
"""

import os
import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSizePolicy, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


class ClipPreviewWidget(QWidget):
    """Video + audio preview; shows first frame before play is pressed."""

    clip_ended = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.clip_path = None
        self._seeking = False
        self._first_frame: QPixmap | None = None

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

    # ------------------------------------------------------------------ UI

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Index 0 — static label: first frame thumbnail or message text
        # Index 1 — live video widget (active during playback)
        self._display_stack = QStackedWidget()

        self.video_display = QLabel("No clip selected")
        self.video_display.setMinimumSize(400, 225)
        self.video_display.setStyleSheet(
            "border: 1px solid #2a2d35; background-color: #0a0c10; color: #6b7280;"
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

        # Controls
        ctrl = QHBoxLayout()

        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        ctrl.addWidget(self.play_pause_btn)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.seek_slider.setEnabled(False)
        ctrl.addWidget(self.seek_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        ctrl.addWidget(self.time_label)

        layout.addLayout(ctrl)

        self.info_label = QLabel("No clip loaded")
        self.info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.info_label)

    # ------------------------------------------------------------------ public API

    def load_clip(self, clip_path: str) -> bool:
        if not os.path.exists(clip_path):
            self.show_message("Clip file not found")
            return False

        self.player.stop()
        self.clip_path = clip_path

        # Extract and show first frame immediately (before user presses play)
        self._first_frame = self._extract_first_frame(clip_path)
        if self._first_frame:
            self._render_first_frame()
        else:
            self.video_display.setText("")
        self._display_stack.setCurrentIndex(0)

        # Queue media source — playback starts only when toggle_play_pause is called
        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(clip_path)))
        self.play_pause_btn.setEnabled(True)
        self.seek_slider.setEnabled(True)
        return True

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
                # First play — switch from thumbnail to live video widget
                self._display_stack.setCurrentIndex(1)
                self.player.play()

    def clear(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.clip_path = None
        self._first_frame = None
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setText("▶")
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.time_label.setText("00:00 / 00:00")
        self.info_label.setText("No clip loaded")
        self.show_message("No clip selected")

    # ------------------------------------------------------------------ first frame

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

    # ------------------------------------------------------------------ slots

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        self._seeking = False
        self.player.setPosition(self.seek_slider.value())

    def _on_position_changed(self, pos_ms: int):
        if not self._seeking:
            self.seek_slider.setValue(pos_ms)
        self._update_time(pos_ms)

    def _on_duration_changed(self, dur_ms: int):
        self.seek_slider.setRange(0, max(0, dur_ms))
        self.info_label.setText(f"Duration: {dur_ms / 1000:.1f}s")

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
            f"{int(ps // 60):02d}:{int(ps % 60):02d} / "
            f"{int(ds // 60):02d}:{int(ds % 60):02d}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._display_stack.currentIndex() == 0 and self._first_frame:
            self._render_first_frame()
