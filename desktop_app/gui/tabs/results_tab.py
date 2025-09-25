"""
Results tab for managing and previewing generated clips.
"""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QListWidget, QListWidgetItem, QGroupBox,
                            QMessageBox, QFileDialog, QSplitter, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.widgets.clip_preview import ClipPreviewWidget


class ResultsTab(QWidget):
    """Results tab for clip management."""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.clips_data = []
        self.init_ui()
        self.load_results()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📊 Results & Clips")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_results)
        controls_layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("📤 Export Selected")
        self.export_btn.clicked.connect(self.export_selected)
        controls_layout.addWidget(self.export_btn)
        
        self.open_folder_btn = QPushButton("📁 Open Folder")
        self.open_folder_btn.clicked.connect(self.open_clips_folder)
        controls_layout.addWidget(self.open_folder_btn)
        
        controls_layout.addStretch()
        
        self.clip_count_label = QLabel("No clips found")
        controls_layout.addWidget(self.clip_count_label)
        
        layout.addLayout(controls_layout)
        
        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Clips list and details
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Clips list
        clips_group = QGroupBox("Generated Clips")
        clips_layout = QVBoxLayout()
        
        self.clips_list = QListWidget()
        self.clips_list.itemSelectionChanged.connect(self.on_clip_selected)
        clips_layout.addWidget(self.clips_list)
        
        clips_group.setLayout(clips_layout)
        left_layout.addWidget(clips_group)
        
        # Clip details
        details_group = QGroupBox("Clip Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        left_layout.addWidget(details_group)
        
        main_splitter.addWidget(left_widget)
        
        # Right side: Clip preview
        preview_group = QGroupBox("Clip Preview")
        preview_layout = QVBoxLayout()
        
        self.clip_preview = ClipPreviewWidget()
        preview_layout.addWidget(self.clip_preview)
        
        preview_group.setLayout(preview_layout)
        main_splitter.addWidget(preview_group)
        
        # Set splitter proportions (40% left, 60% right)
        main_splitter.setSizes([400, 600])
        layout.addWidget(main_splitter)
        
        # Statistics section
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_text)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        self.setLayout(layout)
        
    def load_results(self):
        """Load results from the highlights file and clips folder."""
        try:
            config = self.config_manager.load_config()
            data_folder = config.get('data_folder', './data')
            clips_folder = config.get('final_clips_folder', './final_clips')
            
            # Load highlights data
            highlights_path = os.path.join(data_folder, 'ordered_highlights.json')
            if os.path.exists(highlights_path):
                with open(highlights_path, 'r') as f:
                    self.clips_data = json.load(f)
            else:
                self.clips_data = []
            
            # Update clips list
            self.update_clips_list()
            
            # Update statistics
            self.update_statistics()
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load results: {str(e)}")
            
    def update_clips_list(self):
        """Update the clips list widget."""
        self.clips_list.clear()
        
        if not self.clips_data:
            self.clip_count_label.setText("No clips found")
            return
        
        for i, clip in enumerate(self.clips_data):
            # Create list item
            item_text = f"Clip {i+1:04d} - Score: {clip.get('score', 0)}"
            if 'tags' in clip and clip['tags']:
                item_text += f" - Tags: {', '.join(clip['tags'])}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, clip)
            self.clips_list.addItem(item)
        
        self.clip_count_label.setText(f"{len(self.clips_data)} clips found")
        
    def update_statistics(self):
        """Update the statistics display."""
        if not self.clips_data:
            self.stats_text.setPlainText("No data available")
            return
        
        # Calculate statistics
        total_clips = len(self.clips_data)
        total_score = sum(clip.get('score', 0) for clip in self.clips_data)
        avg_score = total_score / total_clips if total_clips > 0 else 0
        
        # Count tags
        tag_counts = {}
        for clip in self.clips_data:
            for tag in clip.get('tags', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Build statistics text
        stats_text = f"Total Clips: {total_clips}\n"
        stats_text += f"Total Score: {total_score}\n"
        stats_text += f"Average Score: {avg_score:.1f}\n\n"
        
        if tag_counts:
            stats_text += "Tag Distribution:\n"
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                stats_text += f"  {tag}: {count}\n"
        
        self.stats_text.setPlainText(stats_text)
        
    def on_clip_selected(self):
        """Handle clip selection."""
        current_item = self.clips_list.currentItem()
        if not current_item:
            self.details_text.clear()
            self.clip_preview.clear()
            return
        
        clip_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Format clip details
        details = f"Clip Details:\n"
        details += f"Score: {clip_data.get('score', 0)}\n"
        details += f"Start Time: {clip_data.get('clip_start', 0):.2f}s\n"
        details += f"End Time: {clip_data.get('clip_end', 0):.2f}s\n"
        details += f"Duration: {clip_data.get('clip_end', 0) - clip_data.get('clip_start', 0):.2f}s\n"
        details += f"Source: {os.path.basename(clip_data.get('source_video', 'Unknown'))}\n"
        
        if 'tags' in clip_data and clip_data['tags']:
            details += f"Tags: {', '.join(clip_data['tags'])}\n"
        
        if 'events_in_window' in clip_data:
            events = clip_data['events_in_window']
            details += f"\nEvents in Window ({len(events)}):\n"
            for event in events[:5]:  # Show first 5 events
                details += f"  - {event.get('type', 'unknown')} at {event.get('timestamp_seconds', 0):.2f}s\n"
            if len(events) > 5:
                details += f"  ... and {len(events) - 5} more events\n"
        
        self.details_text.setPlainText(details)
        
        # Try to load the corresponding video clip
        self.load_clip_for_preview(clip_data)
        
    def load_clip_for_preview(self, clip_data):
        """Load the corresponding video clip for preview."""
        try:
            config = self.config_manager.load_config()
            clips_folder = config.get('final_clips_folder', './final_clips')
            
            # Try to find the clip file
            # The clip filename format is typically: clip_XXXX_description_score_XX.mp4
            clip_index = self.clips_data.index(clip_data) + 1
            score = clip_data.get('score', 0)
            
            # Look for files matching the pattern
            import glob
            pattern = os.path.join(clips_folder, f"clip_{clip_index:04d}_*_score_{score}.mp4")
            matching_files = glob.glob(pattern)
            
            if matching_files:
                clip_path = matching_files[0]
                if self.clip_preview.load_clip(clip_path):
                    return True
            
            # If no exact match, try to find any clip file with the score
            pattern = os.path.join(clips_folder, f"*_score_{score}.mp4")
            matching_files = glob.glob(pattern)
            
            if matching_files:
                clip_path = matching_files[0]
                if self.clip_preview.load_clip(clip_path):
                    return True
            
            # If still no match, show a message
            self.clip_preview.video_display.setText("Clip file not found")
            return False
            
        except Exception as e:
            self.clip_preview.video_display.setText(f"Error loading clip: {str(e)}")
            return False
        
    def export_selected(self):
        """Export selected clips."""
        current_item = self.clips_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a clip to export.")
            return
        
        # For now, just show a message
        QMessageBox.information(self, "Export", "Export functionality will be implemented in Phase 4.")
        
    def open_clips_folder(self):
        """Open the clips folder in the system file manager."""
        try:
            config = self.config_manager.load_config()
            clips_folder = config.get('final_clips_folder', './final_clips')
            
            if os.path.exists(clips_folder):
                import subprocess
                import platform
                
                system = platform.system()
                if system == "Darwin":  # macOS
                    subprocess.run(["open", clips_folder])
                elif system == "Windows":
                    subprocess.run(["explorer", clips_folder])
                else:  # Linux
                    subprocess.run(["xdg-open", clips_folder])
            else:
                QMessageBox.warning(self, "Folder Not Found", f"Clips folder not found: {clips_folder}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open folder: {str(e)}")
