"""
Pipeline tab for executing the CHAOS processing pipeline.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QCheckBox, QGroupBox, QSplitter,
                            QMessageBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from desktop_app.gui.widgets.progress_tracker import ProgressTracker
from desktop_app.gui.widgets.log_viewer import LogViewer
from desktop_app.workers.pipeline_worker import PipelineWorker
from desktop_app.gui.utils.config_manager import ConfigManager


class PipelineTab(QWidget):
    """Pipeline tab for executing processing stages."""
    
    pipeline_finished = pyqtSignal(bool)  # Emits when pipeline finishes
    
    def __init__(self):
        super().__init__()
        self.pipeline_worker = None
        self.config_manager = ConfigManager()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🚀 Pipeline Execution")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Stage selection section
        stages_group = self.create_stages_group()
        layout.addWidget(stages_group)
        
        # Control buttons section
        controls_group = self.create_controls_group()
        layout.addWidget(controls_group)
        
        # Create splitter for progress and logs
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Progress tracker
        self.progress_tracker = ProgressTracker()
        splitter.addWidget(self.progress_tracker)
        
        # Log viewer
        self.log_viewer = LogViewer()
        splitter.addWidget(self.log_viewer)
        
        # Set splitter proportions (60% progress, 40% logs)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)
        
        self.setLayout(layout)
        
    def create_stages_group(self):
        """Create the stage selection group."""
        group = QGroupBox("Pipeline Stages")
        layout = QVBoxLayout()
        
        desc = QLabel("Select which stages to run:")
        layout.addWidget(desc)
        
        # Stage checkboxes
        stages_layout = QHBoxLayout()
        
        self.ingest_cb = QCheckBox("📁 Ingest")
        self.ingest_cb.setChecked(True)
        stages_layout.addWidget(self.ingest_cb)
        
        self.analyze_cb = QCheckBox("🔍 Analyze")
        self.analyze_cb.setChecked(True)
        stages_layout.addWidget(self.analyze_cb)
        
        self.correlate_cb = QCheckBox("🔗 Correlate")
        self.correlate_cb.setChecked(True)
        stages_layout.addWidget(self.correlate_cb)
        
        self.clip_cb = QCheckBox("✂️ Clip")
        self.clip_cb.setChecked(True)
        stages_layout.addWidget(self.clip_cb)
        
        self.summary_cb = QCheckBox("📊 Summary")
        self.summary_cb.setChecked(True)
        stages_layout.addWidget(self.summary_cb)
        
        layout.addLayout(stages_layout)
        
        # Quick selection buttons
        quick_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_stages)
        quick_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_stages)
        quick_layout.addWidget(select_none_btn)
        
        quick_layout.addStretch()
        layout.addLayout(quick_layout)
        
        group.setLayout(layout)
        return group
        
    def create_controls_group(self):
        """Create the control buttons group."""
        group = QGroupBox("Pipeline Controls")
        layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start Pipeline")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_btn.clicked.connect(self.start_pipeline)
        layout.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.pause_btn.clicked.connect(self.pause_pipeline)
        layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_pipeline)
        layout.addWidget(self.stop_btn)
        
        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self.reset_pipeline)
        layout.addWidget(self.reset_btn)
        
        layout.addStretch()
        
        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(self.status_label)
        
        group.setLayout(layout)
        return group
        
    def get_selected_stages(self):
        """Get list of selected stages."""
        stages = []
        if self.ingest_cb.isChecked():
            stages.append("ingest")
        if self.analyze_cb.isChecked():
            stages.append("analyze")
        if self.correlate_cb.isChecked():
            stages.append("correlate")
        if self.clip_cb.isChecked():
            stages.append("clip")
        if self.summary_cb.isChecked():
            stages.append("summary")
        return stages
        
    def select_all_stages(self):
        """Select all stages."""
        self.ingest_cb.setChecked(True)
        self.analyze_cb.setChecked(True)
        self.correlate_cb.setChecked(True)
        self.clip_cb.setChecked(True)
        self.summary_cb.setChecked(True)
        
    def select_no_stages(self):
        """Deselect all stages."""
        self.ingest_cb.setChecked(False)
        self.analyze_cb.setChecked(False)
        self.correlate_cb.setChecked(False)
        self.clip_cb.setChecked(False)
        self.summary_cb.setChecked(False)
        
    def start_pipeline(self):
        """Start pipeline execution."""
        selected_stages = self.get_selected_stages()
        
        if not selected_stages:
            QMessageBox.warning(self, "No Stages Selected", "Please select at least one stage to run.")
            return
        
        # Validate configuration
        try:
            config = self.config_manager.load_config()
            errors = self.config_manager.validate_config(config)
            if errors:
                QMessageBox.warning(self, "Configuration Errors", 
                                  "Please fix configuration errors before running pipeline:\n\n" + "\n".join(errors))
                return
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", f"Failed to load configuration: {str(e)}")
            return
        
        # Create and start worker
        self.pipeline_worker = PipelineWorker(selected_stages)
        
        # Connect signals
        self.pipeline_worker.progress_updated.connect(self.update_progress)
        self.pipeline_worker.stage_started.connect(self.stage_started)
        self.pipeline_worker.stage_completed.connect(self.stage_completed)
        self.pipeline_worker.log_message.connect(self.add_log_message)
        self.pipeline_worker.error_occurred.connect(self.handle_error)
        self.pipeline_worker.finished.connect(self.pipeline_finished)
        
        # Update UI
        self.progress_tracker.set_stages(selected_stages)
        self.progress_tracker.reset()
        self.log_viewer.clear_log()
        
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running")
        self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        
        # Start worker
        self.pipeline_worker.start()
        self.add_log_message("Pipeline started", "info")
        
    def pause_pipeline(self):
        """Pause/resume pipeline execution."""
        if self.pipeline_worker:
            if self.pipeline_worker.is_paused:
                self.pipeline_worker.resume()
                self.pause_btn.setText("⏸️ Pause")
                self.status_label.setText("Running")
                self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
            else:
                self.pipeline_worker.pause()
                self.pause_btn.setText("▶️ Resume")
                self.status_label.setText("Paused")
                self.status_label.setStyleSheet("font-weight: bold; color: #ff9800;")
                
    def stop_pipeline(self):
        """Stop pipeline execution."""
        if self.pipeline_worker:
            self.pipeline_worker.stop()
            self.add_log_message("Pipeline stop requested", "warning")
            
    def reset_pipeline(self):
        """Reset pipeline state."""
        if self.pipeline_worker and self.pipeline_worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "Reset Pipeline", 
                "Pipeline is currently running. Stop and reset?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.pipeline_worker.stop()
                self.pipeline_worker.wait()  # Wait for thread to finish
        
        # Reset UI
        self.progress_tracker.reset()
        self.log_viewer.clear_log()
        
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸️ Pause")
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: #666;")
        
    def update_progress(self, progress, status):
        """Update progress display."""
        self.progress_tracker.update_overall_progress(progress, status)
        
    def stage_started(self, stage):
        """Handle stage start."""
        self.progress_tracker.update_stage_progress(stage, 0, "Starting...")
        self.add_log_message(f"Starting {stage} stage", "info")
        
    def stage_completed(self, stage, success):
        """Handle stage completion."""
        if success:
            self.progress_tracker.complete_stage(stage, True)
            self.add_log_message(f"Stage '{stage}' completed successfully", "success")
        else:
            self.progress_tracker.complete_stage(stage, False)
            self.add_log_message(f"Stage '{stage}' failed", "error")
            
    def add_log_message(self, message, level="info"):
        """Add message to log viewer."""
        self.log_viewer.add_message(message, level)
        
    def handle_error(self, error_message):
        """Handle pipeline error."""
        self.add_log_message(f"Error: {error_message}", "error")
        
    def pipeline_finished(self, success):
        """Handle pipeline completion."""
        # Update UI
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸️ Pause")
        self.stop_btn.setEnabled(False)
        
        if success:
            self.status_label.setText("Completed")
            self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
            self.add_log_message("Pipeline completed successfully!", "success")
        else:
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet("font-weight: bold; color: #f44336;")
            self.add_log_message("Pipeline failed", "error")
        
        # Emit signal
        self.pipeline_finished.emit(success)
