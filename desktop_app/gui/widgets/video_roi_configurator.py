"""
Video ROI configurator widget for drag-and-drop region of interest setup.
"""

import cv2
import numpy as np
import glob
import os
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QSlider, QFileDialog, QMessageBox,
                            QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QImage, QFont

from desktop_app.gui.utils.config_manager import ConfigManager


class VideoDisplayWidget(QLabel):
    """Interactive video display widget for ROI configuration."""
    
    roi_dragged = pyqtSignal(str, list)  # roi_type, coordinates
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 450)
        self.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Load a video to configure ROI regions")
        self.setScaledContents(True)
        
        # Dragging state
        self.dragging = False
        self.drag_start = None
        self.current_roi_type = None
        self.current_pixmap = None
        
        # ROI rectangles
        self.killfeed_roi = None
        self.chat_roi = None
        
    def set_pixmap(self, pixmap):
        """Set video frame with ROI overlays."""
        self.current_pixmap = pixmap
        self.update_display()
        
    def update_display(self):
        """Update the display with current frame and ROI overlays."""
        if self.current_pixmap is None:
            return
            
        # Create a copy of the pixmap for drawing
        display_pixmap = self.current_pixmap.copy()
        painter = QPainter(display_pixmap)
        
        # Draw killfeed ROI
        if self.killfeed_roi:
            self.draw_roi_overlay(painter, self.killfeed_roi, "Killfeed", QColor(255, 0, 0, 100))
        
        # Draw chat ROI
        if self.chat_roi:
            self.draw_roi_overlay(painter, self.chat_roi, "Chat", QColor(0, 255, 0, 100))
        
        painter.end()
        
        # Update display
        self.setPixmap(display_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
    def draw_roi_overlay(self, painter, roi, label, color):
        """Draw ROI rectangle with label."""
        x1, y1, x2, y2 = roi
        rect = QRect(x1, y1, x2 - x1, y2 - y1)
        
        # Draw semi-transparent rectangle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawRect(rect)
        
        # Draw label
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        
    def set_roi(self, roi_type, coordinates):
        """Set ROI coordinates."""
        if roi_type == "killfeed":
            self.killfeed_roi = coordinates
        elif roi_type == "chat":
            self.chat_roi = coordinates
        self.update_display()
        
    def get_roi(self, roi_type):
        """Get ROI coordinates."""
        if roi_type == "killfeed":
            return self.killfeed_roi
        elif roi_type == "chat":
            return self.chat_roi
        return None
        
    def mousePressEvent(self, event):
        """Start ROI dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.current_pixmap:
            self.dragging = True
            self.drag_start = event.pos()
            
            # Determine which ROI to create based on click position
            # Top-right area = killfeed, bottom-left = chat
            if event.pos().x() > self.width() * 0.6 and event.pos().y() < self.height() * 0.4:
                self.current_roi_type = "killfeed"
            elif event.pos().x() < self.width() * 0.4 and event.pos().y() > self.height() * 0.6:
                self.current_roi_type = "chat"
            else:
                self.current_roi_type = None
                
    def mouseMoveEvent(self, event):
        """Update ROI while dragging."""
        if self.dragging and self.current_roi_type and self.drag_start:
            # Calculate ROI coordinates
            x1 = min(self.drag_start.x(), event.pos().x())
            y1 = min(self.drag_start.y(), event.pos().y())
            x2 = max(self.drag_start.x(), event.pos().x())
            y2 = max(self.drag_start.y(), event.pos().y())
            
            # Set ROI and emit signal
            self.set_roi(self.current_roi_type, [x1, y1, x2, y2])
            self.roi_dragged.emit(self.current_roi_type, [x1, y1, x2, y2])
            
    def mouseReleaseEvent(self, event):
        """Finish ROI dragging."""
        if self.dragging and self.current_roi_type and self.drag_start:
            # Final ROI coordinates
            x1 = min(self.drag_start.x(), event.pos().x())
            y1 = min(self.drag_start.y(), event.pos().y())
            x2 = max(self.drag_start.x(), event.pos().x())
            y2 = max(self.drag_start.y(), event.pos().y())
            
            # Set final ROI
            self.set_roi(self.current_roi_type, [x1, y1, x2, y2])
            self.roi_dragged.emit(self.current_roi_type, [x1, y1, x2, y2])
            
        self.dragging = False
        self.drag_start = None
        self.current_roi_type = None


class VideoROIConfigurator(QWidget):
    """Video ROI configurator with video player and drag-and-drop ROI setup."""
    
    roi_changed = pyqtSignal(dict)  # Emits ROI data when changed
    
    def __init__(self):
        super().__init__()
        self.video_cap = None
        self.current_frame = None
        self.current_frame_number = 0
        self.total_frames = 0
        self.fps = 30
        self.config_manager = ConfigManager()
        
        # ROI rectangles
        self.killfeed_roi = None
        self.chat_roi = None
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Video source selection
        source_layout = QHBoxLayout()
        self.auto_detect_btn = QPushButton("Auto-detect first video")
        self.browse_btn = QPushButton("Browse...")
        self.video_path_label = QLabel("No video selected")
        self.video_path_label.setStyleSheet("color: #666; font-style: italic;")
        
        source_layout.addWidget(self.auto_detect_btn)
        source_layout.addWidget(self.browse_btn)
        source_layout.addWidget(self.video_path_label)
        source_layout.addStretch()
        
        # Video controls
        controls_layout = QHBoxLayout()
        self.play_pause_btn = QPushButton("⏸️")
        self.play_pause_btn.setEnabled(False)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setEnabled(False)
        self.time_label = QLabel("00:00 / 00:00")
        self.speed_label = QLabel("1x")
        
        controls_layout.addWidget(self.play_pause_btn)
        controls_layout.addWidget(self.seek_slider)
        controls_layout.addWidget(self.time_label)
        controls_layout.addWidget(self.speed_label)
        
        # Video display
        self.video_display = VideoDisplayWidget()
        self.video_display.roi_dragged.connect(self.on_roi_dragged)
        
        # ROI status
        self.roi_status_label = QLabel("❌ No ROI configured")
        self.roi_status_label.setStyleSheet("font-weight: bold;")
        
        # Action buttons
        action_layout = QHBoxLayout()
        self.reset_btn = QPushButton("Reset ROI")
        self.reset_btn.setEnabled(False)
        self.test_btn = QPushButton("Test Detection")
        self.test_btn.setEnabled(False)
        
        action_layout.addWidget(self.reset_btn)
        action_layout.addWidget(self.test_btn)
        action_layout.addStretch()
        
        # Add to main layout
        layout.addLayout(source_layout)
        layout.addLayout(controls_layout)
        layout.addWidget(self.video_display)
        layout.addWidget(self.roi_status_label)
        layout.addLayout(action_layout)
        
        self.setLayout(layout)
        
        # Connect signals
        self.auto_detect_btn.clicked.connect(self.auto_detect_video)
        self.browse_btn.clicked.connect(self.browse_video)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.seek_slider.valueChanged.connect(self.seek_to_frame)
        self.reset_btn.clicked.connect(self.reset_roi)
        self.test_btn.clicked.connect(self.test_detection)
        
        # Timer for video playback
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.next_frame)
        
    def auto_detect_video(self):
        """Find and load the first video from captures folder."""
        try:
            config = self.config_manager.load_config()
            captures_folder = config.get('captures_folder', '')
            
            if not captures_folder:
                QMessageBox.warning(self, "No Captures Folder", "Please set the captures folder in the file paths section first.")
                return
                
            video_path = self.find_first_video(captures_folder)
            
            if video_path:
                self.load_video(video_path)
            else:
                QMessageBox.information(self, "No Videos Found", f"No video files found in {captures_folder}")
                
        except Exception as e:
            QMessageBox.critical(self, "Auto-detect Error", f"Failed to auto-detect video: {str(e)}")
    
    def find_first_video(self, folder_path):
        """Find the first video file in the given folder."""
        if not os.path.exists(folder_path):
            return None
            
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        for ext in video_extensions:
            pattern = os.path.join(folder_path, f"**/*{ext}")
            video_files = glob.glob(pattern, recursive=True)
            if video_files:
                return video_files[0]
        return None
        
    def browse_video(self):
        """Open video file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )
        
        if file_path:
            self.load_video(file_path)
            
    def load_video(self, video_path):
        """Load video and initialize player."""
        try:
            self.video_cap = cv2.VideoCapture(video_path)
            if not self.video_cap.isOpened():
                QMessageBox.critical(self, "Video Error", f"Could not open video file: {video_path}")
                return
                
            self.total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            
            if self.fps == 0:
                self.fps = 30  # Default FPS
                
            self.seek_slider.setMaximum(self.total_frames - 1)
            self.video_path_label.setText(f"📹 {os.path.basename(video_path)}")
            self.video_path_label.setStyleSheet("color: #000; font-weight: bold;")
            
            # Enable controls
            self.play_pause_btn.setEnabled(True)
            self.seek_slider.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.test_btn.setEnabled(True)
            
            # Load first frame
            self.seek_to_frame(0)
            
        except Exception as e:
            QMessageBox.critical(self, "Video Error", f"Failed to load video: {str(e)}")
            
    def seek_to_frame(self, frame_number):
        """Seek to specific frame and display it."""
        if not self.video_cap:
            return
            
        try:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.video_cap.read()
            
            if ret:
                self.current_frame = frame
                self.current_frame_number = frame_number
                self.update_display()
                self.update_time_label()
                
        except Exception as e:
            print(f"Error seeking to frame: {e}")
            
    def update_display(self):
        """Update the video display with current frame and ROI overlays."""
        if self.current_frame is None:
            return
            
        try:
            # Convert BGR to RGB for Qt
            frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
            height, width, channel = frame_rgb.shape
            bytes_per_line = 3 * width
            
            # Create QImage
            q_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            
            # Update display with ROI overlays
            self.video_display.set_pixmap(pixmap)
            
        except Exception as e:
            print(f"Error updating display: {e}")
            
    def update_time_label(self):
        """Update the time label."""
        if self.fps > 0:
            current_time = self.current_frame_number / self.fps
            total_time = self.total_frames / self.fps
            
            current_str = f"{int(current_time//60):02d}:{int(current_time%60):02d}"
            total_str = f"{int(total_time//60):02d}:{int(total_time%60):02d}"
            
            self.time_label.setText(f"{current_str} / {total_str}")
            
    def toggle_play_pause(self):
        """Toggle video playback."""
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.play_pause_btn.setText("▶️")
        else:
            self.play_timer.start(int(1000 / self.fps))
            self.play_pause_btn.setText("⏸️")
            
    def next_frame(self):
        """Advance to next frame during playback."""
        if self.current_frame_number < self.total_frames - 1:
            self.seek_to_frame(self.current_frame_number + 1)
        else:
            self.play_timer.stop()
            self.play_pause_btn.setText("▶️")
            
    def on_roi_dragged(self, roi_type, coordinates):
        """Handle ROI drag events from video display."""
        if roi_type == "killfeed":
            self.killfeed_roi = coordinates
        elif roi_type == "chat":
            self.chat_roi = coordinates
            
        self.update_roi_status()
        self.emit_roi_changed()
        
    def update_roi_status(self):
        """Update ROI status display."""
        status_parts = []
        
        if self.killfeed_roi:
            status_parts.append(f"✅ Killfeed ROI: {self.killfeed_roi}")
        else:
            status_parts.append("❌ Killfeed ROI: Not set")
            
        if self.chat_roi:
            status_parts.append(f"✅ Chat ROI: {self.chat_roi}")
        else:
            status_parts.append("❌ Chat ROI: Not set")
            
        self.roi_status_label.setText(" | ".join(status_parts))
        
    def emit_roi_changed(self):
        """Emit ROI changed signal."""
        roi_data = self.get_roi_data()
        self.roi_changed.emit(roi_data)
        
    def get_roi_data(self):
        """Get current ROI data."""
        return {
            'killfeed': self.killfeed_roi,
            'chat': self.chat_roi
        }
        
    def set_roi(self, roi_type, coordinates):
        """Set ROI coordinates programmatically."""
        if roi_type == "killfeed":
            self.killfeed_roi = coordinates
        elif roi_type == "chat":
            self.chat_roi = coordinates
            
        self.video_display.set_roi(roi_type, coordinates)
        self.update_roi_status()
        
    def reset_roi(self):
        """Reset all ROI regions."""
        self.killfeed_roi = None
        self.chat_roi = None
        self.video_display.killfeed_roi = None
        self.video_display.chat_roi = None
        self.video_display.update_display()
        self.update_roi_status()
        self.emit_roi_changed()
        
    def test_detection(self):
        """Test ROI detection on current frame."""
        if not self.current_frame or not self.killfeed_roi or not self.chat_roi:
            QMessageBox.warning(self, "Test Error", "Please configure both ROI regions first")
            return None
            
        try:
            # Extract ROI regions
            killfeed_crop = self.extract_roi(self.current_frame, self.killfeed_roi)
            chat_crop = self.extract_roi(self.current_frame, self.chat_roi)
            
            # Basic analysis
            results = {
                'killfeed': {
                    'size': killfeed_crop.shape,
                    'mean_color': np.mean(killfeed_crop, axis=(0, 1)).tolist()
                },
                'chat': {
                    'size': chat_crop.shape,
                    'mean_color': np.mean(chat_crop, axis=(0, 1)).tolist()
                }
            }
            
            return results
            
        except Exception as e:
            QMessageBox.critical(self, "Test Error", f"Failed to test ROI detection: {str(e)}")
            return None
            
    def extract_roi(self, frame, roi):
        """Extract ROI region from frame."""
        x1, y1, x2, y2 = roi
        return frame[y1:y2, x1:x2]
