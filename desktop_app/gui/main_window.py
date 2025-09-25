"""
Main window for the CHAOS desktop application.
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QStatusBar, QLabel, 
                            QVBoxLayout, QWidget, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon

from desktop_app.gui.tabs.setup_tab import SetupTab
from desktop_app.gui.tabs.config_tab import ConfigTab
from desktop_app.gui.tabs.pipeline_tab import PipelineTab
from desktop_app.gui.tabs.results_tab import ResultsTab
from desktop_app.gui.tabs.advanced_tab import AdvancedTab
from desktop_app.gui.utils.config_manager import ConfigManager


class ChaosMainWindow(QMainWindow):
    """Main window for the CHAOS desktop application."""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("CHAOS - CS2 Highlight Analysis & Organization System")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set window icon (if available)
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / "chaos_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.setup_tab = SetupTab()
        self.config_tab = ConfigTab()
        self.pipeline_tab = PipelineTab()
        self.results_tab = ResultsTab()
        self.advanced_tab = AdvancedTab()
        
        # Add tabs to the tab widget
        self.tab_widget.addTab(self.setup_tab, "🔧 Setup")
        self.tab_widget.addTab(self.config_tab, "⚙️ Configure")
        self.tab_widget.addTab(self.pipeline_tab, "🚀 Pipeline")
        self.tab_widget.addTab(self.results_tab, "📊 Results")
        self.tab_widget.addTab(self.advanced_tab, "🔬 Advanced")
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add status labels
        self.status_label = QLabel("Ready")
        self.progress_label = QLabel("")
        self.last_action_label = QLabel("")
        
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.progress_label)
        self.status_bar.addPermanentWidget(self.last_action_label)
        
        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Set initial tab based on setup status
        self.check_setup_status()
        
    def load_config(self):
        """Load configuration and apply to UI."""
        try:
            config = self.config_manager.load_config()
            
            # Apply GUI-specific settings
            gui_config = config.get('gui', {})
            window_size = gui_config.get('window_size', [1200, 800])
            self.resize(window_size[0], window_size[1])
            
            # Update status
            self.update_status("Configuration loaded successfully")
            
        except Exception as e:
            self.show_error(f"Failed to load configuration: {str(e)}")
            
    def check_setup_status(self):
        """Check if setup is complete and set appropriate initial tab."""
        try:
            config = self.config_manager.load_config()
            system_config = config.get('system', {})
            
            # Check if basic setup is complete
            ffmpeg_available = system_config.get('ffmpeg_available', False)
            dependencies_installed = system_config.get('dependencies_installed', False)
            
            if not ffmpeg_available or not dependencies_installed:
                # Setup not complete, show setup tab
                self.tab_widget.setCurrentIndex(0)
                self.update_status("Setup required - please complete system setup")
            else:
                # Setup complete, show configure tab
                self.tab_widget.setCurrentIndex(1)
                self.update_status("Ready - configure your settings")
                
        except Exception as e:
            # Error loading config, show setup tab
            self.tab_widget.setCurrentIndex(0)
            self.update_status(f"Setup required - error: {str(e)}")
            
    def on_tab_changed(self, index):
        """Handle tab change events."""
        tab_names = ["Setup", "Configure", "Pipeline", "Results", "Advanced"]
        if 0 <= index < len(tab_names):
            self.update_status(f"Switched to {tab_names[index]} tab")
            
    def update_status(self, message):
        """Update the status bar message."""
        self.status_label.setText(message)
        
    def update_progress(self, progress_text):
        """Update the progress indicator."""
        self.progress_label.setText(progress_text)
        
    def update_last_action(self, action):
        """Update the last action indicator."""
        self.last_action_label.setText(f"Last: {action}")
        
    def show_error(self, message):
        """Show an error message dialog."""
        QMessageBox.critical(self, "Error", message)
        
    def show_info(self, message):
        """Show an information message dialog."""
        QMessageBox.information(self, "Information", message)
        
    def show_warning(self, message):
        """Show a warning message dialog."""
        QMessageBox.warning(self, "Warning", message)
        
    def closeEvent(self, event):
        """Handle application close event."""
        try:
            # Save current window size
            config = self.config_manager.load_config()
            if 'gui' not in config:
                config['gui'] = {}
            config['gui']['window_size'] = [self.width(), self.height()]
            self.config_manager.save_config(config)
            
            event.accept()
        except Exception as e:
            print(f"Error saving configuration on close: {e}")
            event.accept()
