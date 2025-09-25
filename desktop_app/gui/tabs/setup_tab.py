"""
Setup tab for system configuration and dependency installation.
"""

import subprocess
import sys
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QProgressBar, QTextEdit, QGroupBox,
                            QMessageBox, QCheckBox, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon

from desktop_app.gui.utils.system_detector import SystemDetector
from desktop_app.gui.utils.config_manager import ConfigManager


class SetupWorker(QThread):
    """Worker thread for setup operations."""
    
    progress_updated = pyqtSignal(int, str)  # progress, status
    step_completed = pyqtSignal(str, bool)  # step_name, success
    finished = pyqtSignal(bool)  # overall_success
    
    def __init__(self, install_ffmpeg=False, install_dependencies=False):
        super().__init__()
        self.install_ffmpeg = install_ffmpeg
        self.install_dependencies = install_dependencies
        self.config_manager = ConfigManager()
        
    def run(self):
        """Run the setup process."""
        try:
            success = True
            
            # Step 1: Check Python version
            self.progress_updated.emit(10, "Checking Python version...")
            python_ok, python_version = SystemDetector.check_python_version()
            self.step_completed.emit("Python Version", python_ok)
            if not python_ok:
                success = False
            
            # Step 2: Check FFmpeg
            self.progress_updated.emit(20, "Checking FFmpeg...")
            ffmpeg_ok, ffmpeg_info = SystemDetector.check_ffmpeg()
            self.step_completed.emit("FFmpeg", ffmpeg_ok)
            
            # Step 3: Install FFmpeg if needed
            if not ffmpeg_ok and self.install_ffmpeg:
                self.progress_updated.emit(30, "Installing FFmpeg...")
                ffmpeg_install_ok, ffmpeg_msg = SystemDetector.install_ffmpeg()
                self.step_completed.emit("FFmpeg Installation", ffmpeg_install_ok)
                if ffmpeg_install_ok:
                    ffmpeg_ok = True
            
            # Step 4: Check CUDA
            self.progress_updated.emit(40, "Detecting CUDA...")
            cuda_info = SystemDetector.detect_cuda()
            cuda_ok = cuda_info['available']
            self.step_completed.emit("CUDA", cuda_ok)
            
            # Step 5: Check dependencies
            self.progress_updated.emit(50, "Checking dependencies...")
            dependencies = SystemDetector.check_dependencies()
            missing_deps = [dep for dep, installed in dependencies.items() if not installed]
            deps_ok = len(missing_deps) == 0
            self.step_completed.emit("Dependencies", deps_ok)
            
            # Step 6: Install dependencies if needed
            if not deps_ok and self.install_dependencies:
                self.progress_updated.emit(60, "Installing dependencies...")
                deps_install_ok = self._install_dependencies()
                self.step_completed.emit("Dependency Installation", deps_install_ok)
                if deps_install_ok:
                    deps_ok = True
            
            # Step 7: Update configuration
            self.progress_updated.emit(80, "Updating configuration...")
            self._update_config(ffmpeg_ok, cuda_info, deps_ok)
            
            # Step 8: Final check
            self.progress_updated.emit(90, "Final verification...")
            final_success = python_ok and ffmpeg_ok and deps_ok
            
            self.progress_updated.emit(100, "Setup complete!")
            self.finished.emit(final_success)
            
        except Exception as e:
            self.progress_updated.emit(0, f"Setup failed: {str(e)}")
            self.finished.emit(False)
    
    def _install_dependencies(self) -> bool:
        """Install missing dependencies."""
        try:
            # Install PyQt6 first
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "PyQt6>=6.5.0", "PyQt6-tools>=6.5.0"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                return False
            
            # Install other dependencies
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "Pillow>=10.0.0", "psutil>=5.9.0"
            ], capture_output=True, text=True, timeout=300)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _update_config(self, ffmpeg_ok: bool, cuda_info: dict, deps_ok: bool):
        """Update configuration with setup results."""
        try:
            config = self.config_manager.load_config()
            
            # Update system settings
            if 'system' not in config:
                config['system'] = {}
            
            config['system']['ffmpeg_available'] = ffmpeg_ok
            config['system']['cuda_available'] = cuda_info['available']
            config['system']['pytorch_version'] = 'cuda' if cuda_info['available'] else 'cpu'
            config['system']['dependencies_installed'] = deps_ok
            
            if cuda_info['available']:
                config['system']['cuda_version'] = cuda_info['version']
                config['system']['cuda_device_count'] = cuda_info['device_count']
                config['system']['cuda_device_name'] = cuda_info['device_name']
            
            self.config_manager.save_config(config)
            
        except Exception as e:
            print(f"Error updating config: {e}")


class SetupTab(QWidget):
    """Setup tab for system configuration."""
    
    def __init__(self):
        super().__init__()
        self.setup_worker = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🔧 System Setup")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Description
        desc = QLabel("This setup will check your system requirements and install necessary dependencies.")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        # System requirements group
        req_group = QGroupBox("System Requirements")
        req_layout = QVBoxLayout()
        
        self.requirements_list = QTextEdit()
        self.requirements_list.setMaximumHeight(200)
        self.requirements_list.setReadOnly(True)
        req_layout.addWidget(self.requirements_list)
        
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)
        
        # Setup options
        options_group = QGroupBox("Setup Options")
        options_layout = QVBoxLayout()
        
        self.install_ffmpeg_cb = QCheckBox("Install FFmpeg automatically (if not found)")
        self.install_ffmpeg_cb.setChecked(True)
        options_layout.addWidget(self.install_ffmpeg_cb)
        
        self.install_deps_cb = QCheckBox("Install missing Python dependencies")
        self.install_deps_cb.setChecked(True)
        options_layout.addWidget(self.install_deps_cb)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Progress section
        progress_group = QGroupBox("Setup Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to start setup")
        progress_layout.addWidget(self.status_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start Setup")
        self.start_btn.clicked.connect(self.start_setup)
        button_layout.addWidget(self.start_btn)
        
        self.check_btn = QPushButton("🔍 Check System")
        self.check_btn.clicked.connect(self.check_system)
        button_layout.addWidget(self.check_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_requirements)
        button_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(button_layout)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Initial system check
        self.refresh_requirements()
        
    def refresh_requirements(self):
        """Refresh the system requirements display."""
        try:
            # Get system info
            python_ok, python_version = SystemDetector.check_python_version()
            ffmpeg_ok, ffmpeg_info = SystemDetector.check_ffmpeg()
            cuda_info = SystemDetector.detect_cuda()
            dependencies = SystemDetector.check_dependencies()
            system_info = SystemDetector.get_system_info()
            disk_info = SystemDetector.check_disk_space()
            
            # Build requirements text
            requirements_text = []
            requirements_text.append("=== SYSTEM INFORMATION ===")
            requirements_text.append(f"Platform: {system_info['platform']}")
            requirements_text.append(f"Python: {python_version} {'✅' if python_ok else '❌'}")
            
            if disk_info and 'free_gb' in disk_info:
                requirements_text.append(f"Free Disk Space: {disk_info['free_gb']} GB")
            
            requirements_text.append("\n=== REQUIREMENTS CHECK ===")
            requirements_text.append(f"Python 3.8+: {'✅' if python_ok else '❌'}")
            requirements_text.append(f"FFmpeg: {'✅' if ffmpeg_ok else '❌'}")
            if not ffmpeg_ok:
                requirements_text.append(f"  └─ {ffmpeg_info}")
            
            requirements_text.append(f"CUDA: {'✅' if cuda_info['available'] else '❌'}")
            if cuda_info['available']:
                requirements_text.append(f"  └─ Version: {cuda_info['version']}")
                requirements_text.append(f"  └─ Device: {cuda_info['device_name']}")
            
            requirements_text.append("\n=== DEPENDENCIES ===")
            missing_deps = []
            for dep, installed in dependencies.items():
                status = "✅" if installed else "❌"
                requirements_text.append(f"{dep}: {status}")
                if not installed:
                    missing_deps.append(dep)
            
            if missing_deps:
                requirements_text.append(f"\nMissing: {', '.join(missing_deps)}")
            
            self.requirements_list.setPlainText("\n".join(requirements_text))
            
        except Exception as e:
            self.requirements_list.setPlainText(f"Error checking system: {str(e)}")
    
    def check_system(self):
        """Perform a quick system check."""
        self.refresh_requirements()
        QMessageBox.information(self, "System Check", "System check completed. See requirements above.")
    
    def start_setup(self):
        """Start the setup process."""
        if self.setup_worker and self.setup_worker.isRunning():
            QMessageBox.warning(self, "Setup Running", "Setup is already running. Please wait for it to complete.")
            return
        
        # Disable start button
        self.start_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Create and start worker
        self.setup_worker = SetupWorker(
            install_ffmpeg=self.install_ffmpeg_cb.isChecked(),
            install_dependencies=self.install_deps_cb.isChecked()
        )
        
        self.setup_worker.progress_updated.connect(self.update_progress)
        self.setup_worker.step_completed.connect(self.step_completed)
        self.setup_worker.finished.connect(self.setup_finished)
        
        self.setup_worker.start()
    
    def update_progress(self, progress: int, status: str):
        """Update progress bar and status."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)
    
    def step_completed(self, step_name: str, success: bool):
        """Handle step completion."""
        status = "✅" if success else "❌"
        current_text = self.requirements_list.toPlainText()
        
        # Update the requirements display with step results
        if f"{step_name}:" in current_text:
            lines = current_text.split('\n')
            for i, line in enumerate(lines):
                if step_name in line and ":" in line:
                    lines[i] = f"{step_name}: {status}"
                    break
            self.requirements_list.setPlainText('\n'.join(lines))
    
    def setup_finished(self, success: bool):
        """Handle setup completion."""
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        
        if success:
            self.status_label.setText("✅ Setup completed successfully!")
            QMessageBox.information(
                self, 
                "Setup Complete", 
                "System setup completed successfully!\n\nYou can now proceed to the Configure tab."
            )
        else:
            self.status_label.setText("❌ Setup failed. Check the requirements above.")
            QMessageBox.warning(
                self, 
                "Setup Failed", 
                "Setup failed. Please check the system requirements and try again."
            )
        
        # Refresh requirements to show final state
        self.refresh_requirements()
