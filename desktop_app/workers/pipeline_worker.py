"""
Background worker for executing the CHAOS processing pipeline.
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chaos_lib import ingestion, analyzers, correlator, clipper, summary
from desktop_app.gui.utils.config_manager import ConfigManager


class PipelineWorker(QThread):
    """Background worker for pipeline execution."""
    
    # Signals
    progress_updated = pyqtSignal(int, str)  # progress_percent, status_message
    stage_started = pyqtSignal(str)  # stage_name
    stage_completed = pyqtSignal(str, bool)  # stage_name, success
    log_message = pyqtSignal(str)  # log_message
    error_occurred = pyqtSignal(str)  # error_message
    finished = pyqtSignal(bool)  # overall_success
    
    def __init__(self, stages: List[str], config_path: str = None):
        super().__init__()
        self.stages = stages
        self.config_path = config_path or str(project_root / "config.yaml")
        self.config_manager = ConfigManager(self.config_path)
        self.is_paused = False
        self.should_stop = False
        
    def run(self):
        """Execute the pipeline stages."""
        try:
            self.log_message.emit("Starting CHAOS pipeline execution...")
            
            # Load configuration
            config = self.config_manager.load_config()
            if not config:
                self.error_occurred.emit("Failed to load configuration")
                self.finished.emit(False)
                return
            
            # Validate configuration
            errors = self.config_manager.validate_config(config)
            if errors:
                self.error_occurred.emit(f"Configuration errors: {'; '.join(errors)}")
                self.finished.emit(False)
                return
            
            # Ensure output directories exist
            os.makedirs(config['data_folder'], exist_ok=True)
            os.makedirs(config['final_clips_folder'], exist_ok=True)
            
            total_stages = len(self.stages)
            overall_success = True
            
            for i, stage in enumerate(self.stages):
                if self.should_stop:
                    self.log_message.emit("Pipeline execution stopped by user")
                    break
                
                # Wait if paused
                while self.is_paused and not self.should_stop:
                    time.sleep(0.1)
                
                if self.should_stop:
                    break
                
                # Calculate progress
                progress = int((i / total_stages) * 100)
                self.progress_updated.emit(progress, f"Starting {stage} stage...")
                self.stage_started.emit(stage)
                
                # Execute stage
                success = self.execute_stage(stage, config)
                self.stage_completed.emit(stage, success)
                
                if not success:
                    overall_success = False
                    self.error_occurred.emit(f"Stage '{stage}' failed")
                    break
                
                self.log_message.emit(f"Stage '{stage}' completed successfully")
            
            # Final progress update
            if not self.should_stop:
                self.progress_updated.emit(100, "Pipeline execution completed!")
                self.log_message.emit("CHAOS pipeline execution finished")
            
            self.finished.emit(overall_success and not self.should_stop)
            
        except Exception as e:
            self.error_occurred.emit(f"Pipeline execution failed: {str(e)}")
            self.finished.emit(False)
    
    def execute_stage(self, stage: str, config: Dict[str, Any]) -> bool:
        """Execute a specific pipeline stage."""
        try:
            if stage == "ingest":
                self.log_message.emit("Creating video manifest...")
                ingestion.create_manifest(config)
                self.log_message.emit("Video manifest created successfully")
                
            elif stage == "analyze":
                self.log_message.emit("Starting video analysis...")
                self.log_message.emit("Initializing AI models (EasyOCR & Whisper)...")
                analyzers.run_analysis(config)
                self.log_message.emit("Video analysis completed")
                
            elif stage == "correlate":
                self.log_message.emit("Correlating events and scoring clips...")
                correlator.run_correlation(config)
                self.log_message.emit("Event correlation completed")
                
            elif stage == "clip":
                self.log_message.emit("Generating video clips...")
                clipper.run_clipping(config)
                self.log_message.emit("Video clipping completed")
                
            elif stage == "summary":
                self.log_message.emit("Generating summary...")
                summary.generate_summary(config)
                self.log_message.emit("Summary generation completed")
                
            else:
                self.log_message.emit(f"Unknown stage: {stage}")
                return False
            
            return True
            
        except Exception as e:
            self.log_message.emit(f"Error in {stage} stage: {str(e)}")
            return False
    
    def pause(self):
        """Pause pipeline execution."""
        self.is_paused = True
        self.log_message.emit("Pipeline execution paused")
    
    def resume(self):
        """Resume pipeline execution."""
        self.is_paused = False
        self.log_message.emit("Pipeline execution resumed")
    
    def stop(self):
        """Stop pipeline execution."""
        self.should_stop = True
        self.log_message.emit("Stopping pipeline execution...")


class CommandLineWorker(QThread):
    """Alternative worker that uses the command-line interface."""
    
    progress_updated = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(bool)
    
    def __init__(self, stages: List[str], config_path: str = None):
        super().__init__()
        self.stages = stages
        self.config_path = config_path or str(project_root / "config.yaml")
        self.should_stop = False
        
    def run(self):
        """Execute pipeline using command-line interface."""
        try:
            self.log_message.emit("Starting pipeline via command-line interface...")
            
            # Determine which stages to run
            if "all" in self.stages or len(self.stages) == 5:
                stage_arg = "all"
            else:
                stage_arg = self.stages[0]  # Run first stage for now
            
            # Build command
            cmd = [
                sys.executable,
                str(project_root / "main.py"),
                stage_arg
            ]
            
            self.log_message.emit(f"Executing command: {' '.join(cmd)}")
            
            # Execute command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output line by line
            while True:
                if self.should_stop:
                    process.terminate()
                    break
                
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                
                if output:
                    self.log_message.emit(output.strip())
            
            # Wait for process to complete
            return_code = process.wait()
            
            if return_code == 0:
                self.progress_updated.emit(100, "Pipeline completed successfully")
                self.finished.emit(True)
            else:
                self.error_occurred.emit(f"Pipeline failed with return code: {return_code}")
                self.finished.emit(False)
                
        except Exception as e:
            self.error_occurred.emit(f"Command execution failed: {str(e)}")
            self.finished.emit(False)
    
    def stop(self):
        """Stop command execution."""
        self.should_stop = True
