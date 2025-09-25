"""
Configuration tab for setting up CHAOS parameters.
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QTextEdit, QGroupBox,
                            QFileDialog, QMessageBox, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.widgets.video_roi_configurator import VideoROIConfigurator


class ConfigTab(QWidget):
    """Configuration tab for application settings."""
    
    config_changed = pyqtSignal(dict)  # Emits when configuration changes
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("⚙️ Configuration")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Create scroll area for the content
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # File paths section
        paths_group = self.create_paths_group()
        scroll_layout.addWidget(paths_group)
        
        # Player names section
        players_group = self.create_players_group()
        scroll_layout.addWidget(players_group)
        
        # ROI configuration section
        roi_group = self.create_roi_group()
        scroll_layout.addWidget(roi_group)
        
        # Action buttons
        buttons_group = self.create_buttons_group()
        scroll_layout.addWidget(buttons_group)
        
        # Add stretch to push everything to the top
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        self.setLayout(layout)
        
    def create_paths_group(self):
        """Create the file paths configuration group."""
        group = QGroupBox("📁 File Paths")
        layout = QVBoxLayout()
        
        # Captures folder
        captures_layout = QHBoxLayout()
        captures_layout.addWidget(QLabel("Captures Folder:"))
        self.captures_edit = QLineEdit()
        self.captures_edit.setPlaceholderText("Select folder containing your CS2 video captures...")
        captures_layout.addWidget(self.captures_edit)
        self.captures_btn = QPushButton("Browse...")
        self.captures_btn.clicked.connect(lambda: self.browse_folder(self.captures_edit))
        captures_layout.addWidget(self.captures_btn)
        layout.addLayout(captures_layout)
        
        # Data folder
        data_layout = QHBoxLayout()
        data_layout.addWidget(QLabel("Data Folder:"))
        self.data_edit = QLineEdit()
        self.data_edit.setPlaceholderText("Folder for intermediate data files...")
        data_layout.addWidget(self.data_edit)
        self.data_btn = QPushButton("Browse...")
        self.data_btn.clicked.connect(lambda: self.browse_folder(self.data_edit))
        data_layout.addWidget(self.data_btn)
        layout.addLayout(data_layout)
        
        # Output folder
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Folder:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Folder for final video clips...")
        output_layout.addWidget(self.output_edit)
        self.output_btn = QPushButton("Browse...")
        self.output_btn.clicked.connect(lambda: self.browse_folder(self.output_edit))
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)
        
        group.setLayout(layout)
        return group
        
    def create_players_group(self):
        """Create the player names configuration group."""
        group = QGroupBox("👥 Player Names")
        layout = QVBoxLayout()
        
        desc = QLabel("Enter your known in-game names (one per line):")
        layout.addWidget(desc)
        
        self.players_edit = QTextEdit()
        self.players_edit.setMaximumHeight(120)
        self.players_edit.setPlaceholderText("stingered by an WAS\nmarmalade sandwich\nIZI KATKA\n...")
        layout.addWidget(self.players_edit)
        
        group.setLayout(layout)
        return group
        
    def create_roi_group(self):
        """Create the ROI configuration group."""
        group = QGroupBox("🎯 Region of Interest Configuration")
        layout = QVBoxLayout()
        
        desc = QLabel("Configure regions of interest for killfeed and chat detection:")
        layout.addWidget(desc)
        
        # Create the video ROI configurator
        self.roi_configurator = VideoROIConfigurator()
        self.roi_configurator.roi_changed.connect(self.on_roi_changed)
        layout.addWidget(self.roi_configurator)
        
        group.setLayout(layout)
        return group
        
    def create_buttons_group(self):
        """Create the action buttons group."""
        group = QGroupBox("Actions")
        layout = QHBoxLayout()
        
        self.test_btn = QPushButton("🧪 Test Configuration")
        self.test_btn.clicked.connect(self.test_configuration)
        layout.addWidget(self.test_btn)
        
        self.save_btn = QPushButton("💾 Save Configuration")
        self.save_btn.clicked.connect(self.save_configuration)
        layout.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("🔄 Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_configuration)
        layout.addWidget(self.reset_btn)
        
        group.setLayout(layout)
        return group
        
    def browse_folder(self, line_edit):
        """Open folder browser dialog."""
        current_path = line_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Folder", 
            current_path
        )
        if folder:
            line_edit.setText(folder)
            self.on_config_changed()
            
    def load_config(self):
        """Load configuration from file."""
        try:
            config = self.config_manager.load_config()
            
            # Load file paths
            self.captures_edit.setText(config.get('captures_folder', ''))
            self.data_edit.setText(config.get('data_folder', './data'))
            self.output_edit.setText(config.get('final_clips_folder', './final_clips'))
            
            # Load player names
            player_names = config.get('player_names', [])
            self.players_edit.setPlainText('\n'.join(player_names))
            
            # Load ROI settings
            killfeed_roi = config.get('killfeed_roi', [1920, 40, 2550, 300])
            chat_roi = config.get('chat_roi', [30, 1150, 650, 1300])
            self.roi_configurator.set_roi('killfeed', killfeed_roi)
            self.roi_configurator.set_roi('chat', chat_roi)
            
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Failed to load configuration: {str(e)}")
            
    def save_configuration(self):
        """Save current configuration."""
        try:
            config = self.config_manager.load_config()
            
            # Save file paths
            config['captures_folder'] = self.captures_edit.text()
            config['data_folder'] = self.data_edit.text()
            config['final_clips_folder'] = self.output_edit.text()
            
            # Save player names
            player_text = self.players_edit.toPlainText().strip()
            config['player_names'] = [name.strip() for name in player_text.split('\n') if name.strip()]
            
            # Save ROI settings
            roi_data = self.roi_configurator.get_roi_data()
            if roi_data:
                config['killfeed_roi'] = roi_data.get('killfeed', [1920, 40, 2550, 300])
                config['chat_roi'] = roi_data.get('chat', [30, 1150, 650, 1300])
            
            # Validate configuration
            errors = self.config_manager.validate_config(config)
            if errors:
                QMessageBox.warning(self, "Configuration Errors", "Please fix the following errors:\n\n" + "\n".join(errors))
                return
            
            # Save configuration
            if self.config_manager.save_config(config):
                QMessageBox.information(self, "Success", "Configuration saved successfully!")
                self.config_changed.emit(config)
            else:
                QMessageBox.warning(self, "Error", "Failed to save configuration.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
            
    def test_configuration(self):
        """Test the current configuration."""
        try:
            # Get current configuration
            config = self.config_manager.load_config()
            
            # Update with current UI values
            config['captures_folder'] = self.captures_edit.text()
            config['data_folder'] = self.data_edit.text()
            config['final_clips_folder'] = self.output_edit.text()
            
            player_text = self.players_edit.toPlainText().strip()
            config['player_names'] = [name.strip() for name in player_text.split('\n') if name.strip()]
            
            roi_data = self.roi_configurator.get_roi_data()
            if roi_data:
                config['killfeed_roi'] = roi_data.get('killfeed', [1920, 40, 2550, 300])
                config['chat_roi'] = roi_data.get('chat', [30, 1150, 650, 1300])
            
            # Validate configuration
            errors = self.config_manager.validate_config(config)
            if errors:
                QMessageBox.warning(self, "Configuration Errors", "Please fix the following errors:\n\n" + "\n".join(errors))
                return
            
            # Test ROI detection if available
            if hasattr(self.roi_configurator, 'test_detection'):
                test_results = self.roi_configurator.test_detection()
                if test_results:
                    QMessageBox.information(self, "Test Results", f"ROI detection test completed:\n\n{test_results}")
                else:
                    QMessageBox.information(self, "Test Results", "ROI detection test completed successfully!")
            else:
                QMessageBox.information(self, "Configuration Test", "Configuration is valid!")
                
        except Exception as e:
            QMessageBox.critical(self, "Test Error", f"Failed to test configuration: {str(e)}")
            
    def reset_configuration(self):
        """Reset configuration to defaults."""
        reply = QMessageBox.question(
            self, 
            "Reset Configuration", 
            "Are you sure you want to reset all settings to defaults? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                default_config = self.config_manager.reset_to_defaults()
                
                # Reset UI to defaults
                self.captures_edit.setText(default_config.get('captures_folder', ''))
                self.data_edit.setText(default_config.get('data_folder', './data'))
                self.output_edit.setText(default_config.get('final_clips_folder', './final_clips'))
                
                player_names = default_config.get('player_names', [])
                self.players_edit.setPlainText('\n'.join(player_names))
                
                # Reset ROI
                self.roi_configurator.set_roi('killfeed', default_config.get('killfeed_roi', [1920, 40, 2550, 300]))
                self.roi_configurator.set_roi('chat', default_config.get('chat_roi', [30, 1150, 650, 1300]))
                
                QMessageBox.information(self, "Reset Complete", "Configuration has been reset to defaults.")
                
            except Exception as e:
                QMessageBox.critical(self, "Reset Error", f"Failed to reset configuration: {str(e)}")
                
    def on_roi_changed(self, roi_data):
        """Handle ROI changes."""
        self.on_config_changed()
        
    def on_config_changed(self):
        """Handle configuration changes."""
        # This could be used to enable/disable save button or show unsaved changes indicator
        pass
