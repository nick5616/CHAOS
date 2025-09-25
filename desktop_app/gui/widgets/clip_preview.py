"""
Clip preview widget for playing generated video clips.
"""

import os
import cv2
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QSlider, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage


class ClipPreviewWidget(QWidget):
    """Widget for previewing video clips."""
    
    def __init__(self):
        super().__init__()
        self.video_cap = None
        self.current_frame = None
        self.current_frame_number = 0
        self.total_frames = 0
        self.fps = 30
        self.is_playing = False
        self.clip_path = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Video display
        self.video_display = QLabel()
        self.video_display.setMinimumSize(400, 225)  # 16:9 aspect ratio
        self.video_display.setStyleSheet("border: 1px solid gray; background-color: black;")
        self.video_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_display.setText("No clip selected")
        self.video_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_display)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("▶️")
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        controls_layout.addWidget(self.play_pause_btn)
        
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self.seek_to_frame)
        self.seek_slider.setEnabled(False)
        controls_layout.addWidget(self.seek_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        controls_layout.addWidget(self.time_label)
        
        layout.addLayout(controls_layout)
        
        # Info
        self.info_label = QLabel("No clip loaded")
        self.info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
        
        # Timer for video playback
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.next_frame)
        
    def load_clip(self, clip_path: str):
        """Load a video clip for preview."""
        if not os.path.exists(clip_path):
            self.video_display.setText("Clip file not found")
            return False
            
        # Release previous video
        if self.video_cap:
            self.video_cap.release()
            
        self.video_cap = cv2.VideoCapture(clip_path)
        if not self.video_cap.isOpened():
            self.video_display.setText("Could not open video file")
            return False
            
        self.clip_path = clip_path
        self.total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        if self.fps == 0:
            self.fps = 30  # Default to 30 if not detected
            
        # Update UI
        self.seek_slider.setRange(0, self.total_frames - 1)
        self.seek_slider.setEnabled(True)
        self.play_pause_btn.setEnabled(True)
        
        # Load first frame
        self.seek_to_frame(0)
        
        # Update info
        duration = self.total_frames / self.fps
        self.info_label.setText(f"Duration: {duration:.1f}s | Frames: {self.total_frames} | FPS: {self.fps:.1f}")
        
        return True
        
    def toggle_play_pause(self):
        """Toggle video playback."""
        if not self.video_cap or not self.video_cap.isOpened():
            return
            
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_pause_btn.setText("⏸️")
            self.play_timer.start(int(1000 / self.fps))  # Milliseconds per frame
        else:
            self.play_pause_btn.setText("▶️")
            self.play_timer.stop()
            
    def next_frame(self):
        """Advance to the next frame."""
        if not self.video_cap or not self.video_cap.isOpened():
            return
            
        self.current_frame_number += 1
        if self.current_frame_number >= self.total_frames:
            self.current_frame_number = self.total_frames - 1
            self.toggle_play_pause()  # Stop playback at end
            
        self.seek_to_frame(self.current_frame_number)
        
    def seek_to_frame(self, frame_number):
        """Seek to specific frame and display it."""
        if not self.video_cap or not self.video_cap.isOpened():
            return
            
        self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_cap.read()
        
        if ret:
            self.current_frame = frame
            self.current_frame_number = frame_number
            self.seek_slider.setValue(frame_number)
            self.update_display()
            self.update_time_label()
        else:
            # If seeking fails, try to read next frame (might be end of video)
            self.current_frame_number = self.total_frames - 1
            self.seek_slider.setValue(self.current_frame_number)
            self.update_time_label()
            self.toggle_play_pause()  # Stop playback
            
    def update_display(self):
        """Update the video display with current frame."""
        if self.current_frame is None:
            return
            
        # Convert BGR to RGB for Qt
        frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame_rgb.shape
        bytes_per_line = 3 * width
        
        # Create QImage
        q_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        
        # Scale pixmap to fit widget while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.video_display.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.video_display.setPixmap(scaled_pixmap)
        
    def update_time_label(self):
        """Update the current time / total time label."""
        current_seconds = self.current_frame_number / self.fps
        total_seconds = self.total_frames / self.fps
        
        current_time_str = f"{int(current_seconds // 60):02d}:{int(current_seconds % 60):02d}"
        total_time_str = f"{int(total_seconds // 60):02d}:{int(total_seconds % 60):02d}"
        self.time_label.setText(f"{current_time_str} / {total_time_str}")
        
    def clear(self):
        """Clear the preview."""
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
            
        self.is_playing = False
        self.play_timer.stop()
        self.play_pause_btn.setText("▶️")
        self.play_pause_btn.setEnabled(False)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.time_label.setText("00:00 / 00:00")
        self.info_label.setText("No clip loaded")
        self.video_display.setText("No clip selected")
        self.video_display.setPixmap(QPixmap())
        
    def resizeEvent(self, event):
        """Handle widget resize."""
        super().resizeEvent(event)
        if self.current_frame is not None:
            self.update_display()
