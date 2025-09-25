"""
Progress tracking widget for pipeline execution.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QProgressBar, QGroupBox, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette


class ProgressTracker(QWidget):
    """Widget for tracking pipeline execution progress."""
    
    def __init__(self):
        super().__init__()
        self.current_stage = None
        self.stage_progress = 0
        self.overall_progress = 0
        self.stages = []
        self.completed_stages = set()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Overall progress section
        overall_group = QGroupBox("Overall Progress")
        overall_layout = QVBoxLayout()
        
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        overall_layout.addWidget(self.overall_progress_bar)
        
        self.overall_status_label = QLabel("Ready")
        self.overall_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overall_status_label.setStyleSheet("font-weight: bold; color: #666;")
        overall_layout.addWidget(self.overall_status_label)
        
        overall_group.setLayout(overall_layout)
        layout.addWidget(overall_group)
        
        # Current stage section
        stage_group = QGroupBox("Current Stage")
        stage_layout = QVBoxLayout()
        
        self.stage_name_label = QLabel("No stage running")
        self.stage_name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.stage_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stage_layout.addWidget(self.stage_name_label)
        
        self.stage_progress_bar = QProgressBar()
        self.stage_progress_bar.setRange(0, 100)
        self.stage_progress_bar.setValue(0)
        self.stage_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        stage_layout.addWidget(self.stage_progress_bar)
        
        self.stage_status_label = QLabel("")
        self.stage_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage_status_label.setStyleSheet("color: #666;")
        stage_layout.addWidget(self.stage_status_label)
        
        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group)
        
        # Stage list section
        stages_group = QGroupBox("Pipeline Stages")
        stages_layout = QVBoxLayout()
        
        self.stages_frame = QFrame()
        self.stages_layout = QVBoxLayout(self.stages_frame)
        self.stages_layout.setSpacing(5)
        
        stages_layout.addWidget(self.stages_frame)
        stages_group.setLayout(stages_layout)
        layout.addWidget(stages_group)
        
        self.setLayout(layout)
        
    def set_stages(self, stages: list):
        """Set the list of pipeline stages."""
        self.stages = stages
        self.completed_stages.clear()
        self.update_stages_display()
        
    def update_stages_display(self):
        """Update the stages display."""
        # Clear existing stage labels
        for i in reversed(range(self.stages_layout.count())):
            self.stages_layout.itemAt(i).widget().setParent(None)
        
        # Add stage labels
        for i, stage in enumerate(self.stages):
            stage_label = QLabel(f"{i+1}. {self.format_stage_name(stage)}")
            stage_label.setStyleSheet("padding: 5px; border-radius: 3px;")
            
            if stage in self.completed_stages:
                stage_label.setStyleSheet("""
                    padding: 5px; 
                    border-radius: 3px; 
                    background-color: #4CAF50; 
                    color: white; 
                    font-weight: bold;
                """)
            elif stage == self.current_stage:
                stage_label.setStyleSheet("""
                    padding: 5px; 
                    border-radius: 3px; 
                    background-color: #2196F3; 
                    color: white; 
                    font-weight: bold;
                """)
            else:
                stage_label.setStyleSheet("""
                    padding: 5px; 
                    border-radius: 3px; 
                    background-color: #f0f0f0; 
                    color: #666;
                """)
            
            self.stages_layout.addWidget(stage_label)
    
    def format_stage_name(self, stage: str) -> str:
        """Format stage name for display."""
        stage_names = {
            "ingest": "📁 Video Ingestion",
            "analyze": "🔍 Video Analysis", 
            "correlate": "🔗 Event Correlation",
            "clip": "✂️ Video Clipping",
            "summary": "📊 Summary Generation"
        }
        return stage_names.get(stage, stage.title())
    
    def update_overall_progress(self, progress: int, status: str = ""):
        """Update overall progress."""
        self.overall_progress = progress
        self.overall_progress_bar.setValue(progress)
        
        if status:
            self.overall_status_label.setText(status)
        
        # Update overall status color based on progress
        if progress == 0:
            self.overall_status_label.setStyleSheet("font-weight: bold; color: #666;")
        elif progress == 100:
            self.overall_status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        else:
            self.overall_status_label.setStyleSheet("font-weight: bold; color: #2196F3;")
    
    def update_stage_progress(self, stage: str, progress: int, status: str = ""):
        """Update current stage progress."""
        if stage != self.current_stage:
            # New stage started
            if self.current_stage:
                self.completed_stages.add(self.current_stage)
            self.current_stage = stage
            self.update_stages_display()
        
        self.stage_progress = progress
        self.stage_progress_bar.setValue(progress)
        
        if status:
            self.stage_status_label.setText(status)
        
        # Update stage name
        self.stage_name_label.setText(self.format_stage_name(stage))
    
    def complete_stage(self, stage: str, success: bool = True):
        """Mark a stage as completed."""
        if success:
            self.completed_stages.add(stage)
        else:
            # Mark as failed (could add different styling)
            pass
        
        self.update_stages_display()
        
        # Clear current stage if it was completed
        if stage == self.current_stage:
            self.current_stage = None
            self.stage_name_label.setText("No stage running")
            self.stage_progress_bar.setValue(0)
            self.stage_status_label.setText("")
    
    def reset(self):
        """Reset progress tracker."""
        self.current_stage = None
        self.stage_progress = 0
        self.overall_progress = 0
        self.completed_stages.clear()
        
        self.overall_progress_bar.setValue(0)
        self.overall_status_label.setText("Ready")
        self.overall_status_label.setStyleSheet("font-weight: bold; color: #666;")
        
        self.stage_name_label.setText("No stage running")
        self.stage_progress_bar.setValue(0)
        self.stage_status_label.setText("")
        
        self.update_stages_display()
    
    def get_progress_info(self) -> dict:
        """Get current progress information."""
        return {
            'overall_progress': self.overall_progress,
            'current_stage': self.current_stage,
            'stage_progress': self.stage_progress,
            'completed_stages': list(self.completed_stages),
            'total_stages': len(self.stages)
        }
