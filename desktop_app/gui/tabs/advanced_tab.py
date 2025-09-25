"""
Advanced settings tab for fine-tuning detection parameters.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QSlider, QSpinBox, QDoubleSpinBox, QGroupBox,
                            QPushButton, QMessageBox, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from desktop_app.gui.utils.config_manager import ConfigManager


class AdvancedTab(QWidget):
    """Advanced settings tab for fine-tuning detection parameters."""
    
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
        title = QLabel("🔬 Advanced Settings")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Warning
        warning = QLabel("⚠️ These settings are for advanced users. Incorrect values may cause detection issues.")
        warning.setStyleSheet("color: #ff9800; font-weight: bold; padding: 10px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Create scroll area for the content
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Color detection section
        color_group = self.create_color_detection_group()
        scroll_layout.addWidget(color_group)
        
        # Shape detection section
        shape_group = self.create_shape_detection_group()
        scroll_layout.addWidget(shape_group)
        
        # Timing section
        timing_group = self.create_timing_group()
        scroll_layout.addWidget(timing_group)
        
        # Scoring weights section
        scoring_group = self.create_scoring_group()
        scroll_layout.addWidget(scoring_group)
        
        # Action buttons
        buttons_group = self.create_buttons_group()
        scroll_layout.addWidget(buttons_group)
        
        # Add stretch to push everything to the top
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        self.setLayout(layout)
        
    def create_color_detection_group(self):
        """Create the color detection parameters group."""
        group = QGroupBox("🎨 Color Detection Parameters")
        layout = QVBoxLayout()
        
        # Red HSV Range 1
        red1_layout = QHBoxLayout()
        red1_layout.addWidget(QLabel("Red HSV Range 1:"))
        
        self.red_h_lower1 = self.create_hsv_slider("H Lower", 0, 180, 0)
        self.red_s_lower1 = self.create_hsv_slider("S Lower", 0, 255, 120)
        self.red_v_lower1 = self.create_hsv_slider("V Lower", 0, 255, 70)
        
        red1_layout.addWidget(self.red_h_lower1)
        red1_layout.addWidget(self.red_s_lower1)
        red1_layout.addWidget(self.red_v_lower1)
        
        self.red_h_upper1 = self.create_hsv_slider("H Upper", 0, 180, 10)
        self.red_s_upper1 = self.create_hsv_slider("S Upper", 0, 255, 255)
        self.red_v_upper1 = self.create_hsv_slider("V Upper", 0, 255, 255)
        
        red1_layout.addWidget(self.red_h_upper1)
        red1_layout.addWidget(self.red_s_upper1)
        red1_layout.addWidget(self.red_v_upper1)
        
        layout.addLayout(red1_layout)
        
        # Red HSV Range 2
        red2_layout = QHBoxLayout()
        red2_layout.addWidget(QLabel("Red HSV Range 2:"))
        
        self.red_h_lower2 = self.create_hsv_slider("H Lower", 0, 180, 170)
        self.red_s_lower2 = self.create_hsv_slider("S Lower", 0, 255, 120)
        self.red_v_lower2 = self.create_hsv_slider("V Lower", 0, 255, 70)
        
        red2_layout.addWidget(self.red_h_lower2)
        red2_layout.addWidget(self.red_s_lower2)
        red2_layout.addWidget(self.red_v_lower2)
        
        self.red_h_upper2 = self.create_hsv_slider("H Upper", 0, 180, 180)
        self.red_s_upper2 = self.create_hsv_slider("S Upper", 0, 255, 255)
        self.red_v_upper2 = self.create_hsv_slider("V Upper", 0, 255, 255)
        
        red2_layout.addWidget(self.red_h_upper2)
        red2_layout.addWidget(self.red_s_upper2)
        red2_layout.addWidget(self.red_v_upper2)
        
        layout.addLayout(red2_layout)
        
        # T-side Orange Range
        t_layout = QHBoxLayout()
        t_layout.addWidget(QLabel("T-side Orange Range:"))
        
        self.t_h_lower = self.create_hsv_slider("H Lower", 0, 180, 10)
        self.t_s_lower = self.create_hsv_slider("S Lower", 0, 255, 150)
        self.t_v_lower = self.create_hsv_slider("V Lower", 0, 255, 150)
        
        t_layout.addWidget(self.t_h_lower)
        t_layout.addWidget(self.t_s_lower)
        t_layout.addWidget(self.t_v_lower)
        
        self.t_h_upper = self.create_hsv_slider("H Upper", 0, 180, 25)
        self.t_s_upper = self.create_hsv_slider("S Upper", 0, 255, 255)
        self.t_v_upper = self.create_hsv_slider("V Upper", 0, 255, 255)
        
        t_layout.addWidget(self.t_h_upper)
        t_layout.addWidget(self.t_s_upper)
        t_layout.addWidget(self.t_v_upper)
        
        layout.addLayout(t_layout)
        
        # CT-side Blue Range
        ct_layout = QHBoxLayout()
        ct_layout.addWidget(QLabel("CT-side Blue Range:"))
        
        self.ct_h_lower = self.create_hsv_slider("H Lower", 0, 180, 100)
        self.ct_s_lower = self.create_hsv_slider("S Lower", 0, 255, 150)
        self.ct_v_lower = self.create_hsv_slider("V Lower", 0, 255, 150)
        
        ct_layout.addWidget(self.ct_h_lower)
        ct_layout.addWidget(self.ct_s_lower)
        ct_layout.addWidget(self.ct_v_lower)
        
        self.ct_h_upper = self.create_hsv_slider("H Upper", 0, 180, 130)
        self.ct_s_upper = self.create_hsv_slider("S Upper", 0, 255, 255)
        self.ct_v_upper = self.create_hsv_slider("V Upper", 0, 255, 255)
        
        ct_layout.addWidget(self.ct_h_upper)
        ct_layout.addWidget(self.ct_s_upper)
        ct_layout.addWidget(self.ct_v_upper)
        
        layout.addLayout(ct_layout)
        
        group.setLayout(layout)
        return group
        
    def create_shape_detection_group(self):
        """Create the shape detection parameters group."""
        group = QGroupBox("📏 Shape Detection Parameters")
        layout = QVBoxLayout()
        
        # Height range
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Killfeed Rectangle Height:"))
        
        self.min_height = QSpinBox()
        self.min_height.setRange(10, 100)
        self.min_height.setValue(25)
        self.min_height.valueChanged.connect(self.on_config_changed)
        height_layout.addWidget(QLabel("Min:"))
        height_layout.addWidget(self.min_height)
        
        self.max_height = QSpinBox()
        self.max_height.setRange(20, 200)
        self.max_height.setValue(50)
        self.max_height.valueChanged.connect(self.on_config_changed)
        height_layout.addWidget(QLabel("Max:"))
        height_layout.addWidget(self.max_height)
        
        height_layout.addStretch()
        layout.addLayout(height_layout)
        
        # Aspect ratio
        aspect_layout = QHBoxLayout()
        aspect_layout.addWidget(QLabel("Minimum Aspect Ratio:"))
        
        self.min_aspect_ratio = QDoubleSpinBox()
        self.min_aspect_ratio.setRange(1.0, 20.0)
        self.min_aspect_ratio.setSingleStep(0.1)
        self.min_aspect_ratio.setValue(8.0)
        self.min_aspect_ratio.valueChanged.connect(self.on_config_changed)
        aspect_layout.addWidget(self.min_aspect_ratio)
        
        aspect_layout.addStretch()
        layout.addLayout(aspect_layout)
        
        group.setLayout(layout)
        return group
        
    def create_timing_group(self):
        """Create the timing parameters group."""
        group = QGroupBox("⏱️ Timing Parameters")
        layout = QVBoxLayout()
        
        # Kill memory duration
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("Kill Memory Duration (seconds):"))
        
        self.kill_memory_duration = QDoubleSpinBox()
        self.kill_memory_duration.setRange(1.0, 30.0)
        self.kill_memory_duration.setSingleStep(0.5)
        self.kill_memory_duration.setValue(7.0)
        self.kill_memory_duration.valueChanged.connect(self.on_config_changed)
        memory_layout.addWidget(self.kill_memory_duration)
        
        memory_layout.addStretch()
        layout.addLayout(memory_layout)
        
        # OCR frame step
        ocr_layout = QHBoxLayout()
        ocr_layout.addWidget(QLabel("OCR Frame Step:"))
        
        self.ocr_frame_step = QSpinBox()
        self.ocr_frame_step.setRange(1, 100)
        self.ocr_frame_step.setValue(30)
        self.ocr_frame_step.valueChanged.connect(self.on_config_changed)
        ocr_layout.addWidget(self.ocr_frame_step)
        
        ocr_layout.addStretch()
        layout.addLayout(ocr_layout)
        
        # Clip buffer times
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("Clip Buffer Times (seconds):"))
        
        self.pre_buffer = QDoubleSpinBox()
        self.pre_buffer.setRange(0.0, 30.0)
        self.pre_buffer.setSingleStep(0.5)
        self.pre_buffer.setValue(7.0)
        self.pre_buffer.valueChanged.connect(self.on_config_changed)
        buffer_layout.addWidget(QLabel("Pre:"))
        buffer_layout.addWidget(self.pre_buffer)
        
        self.post_buffer = QDoubleSpinBox()
        self.post_buffer.setRange(0.0, 30.0)
        self.post_buffer.setSingleStep(0.5)
        self.post_buffer.setValue(8.0)
        self.post_buffer.valueChanged.connect(self.on_config_changed)
        buffer_layout.addWidget(QLabel("Post:"))
        buffer_layout.addWidget(self.post_buffer)
        
        buffer_layout.addStretch()
        layout.addLayout(buffer_layout)
        
        group.setLayout(layout)
        return group
        
    def create_scoring_group(self):
        """Create the scoring weights group."""
        group = QGroupBox("🎯 Scoring Weights")
        layout = QVBoxLayout()
        
        # Kill weight
        kill_layout = QHBoxLayout()
        kill_layout.addWidget(QLabel("Kill Weight:"))
        self.kill_weight = self.create_weight_slider(0, 50, 10)
        kill_layout.addWidget(self.kill_weight)
        layout.addLayout(kill_layout)
        
        # Multi-kill bonus
        multi_layout = QHBoxLayout()
        multi_layout.addWidget(QLabel("Multi-kill Bonus:"))
        self.multi_kill_bonus = self.create_weight_slider(0, 50, 15)
        multi_layout.addWidget(self.multi_kill_bonus)
        layout.addLayout(multi_layout)
        
        # Team hype voice
        hype_layout = QHBoxLayout()
        hype_layout.addWidget(QLabel("Team Hype Voice:"))
        self.team_hype_voice = self.create_weight_slider(0, 50, 20)
        hype_layout.addWidget(self.team_hype_voice)
        layout.addLayout(hype_layout)
        
        # Enemy rage chat
        rage_layout = QHBoxLayout()
        rage_layout.addWidget(QLabel("Enemy Rage Chat:"))
        self.enemy_rage_chat = self.create_weight_slider(0, 50, 25)
        rage_layout.addWidget(self.enemy_rage_chat)
        layout.addLayout(rage_layout)
        
        # Audio spike
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("Audio Spike:"))
        self.audio_spike = self.create_weight_slider(0, 50, 5)
        audio_layout.addWidget(self.audio_spike)
        layout.addLayout(audio_layout)
        
        group.setLayout(layout)
        return group
        
    def create_buttons_group(self):
        """Create the action buttons group."""
        group = QGroupBox("Actions")
        layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("🔄 Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        layout.addWidget(self.reset_btn)
        
        self.test_btn = QPushButton("🧪 Test Settings")
        self.test_btn.clicked.connect(self.test_settings)
        layout.addWidget(self.test_btn)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
        
    def create_hsv_slider(self, label, min_val, max_val, default_val):
        """Create an HSV parameter slider."""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(label_widget)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.valueChanged.connect(self.on_config_changed)
        layout.addWidget(slider)
        
        value_label = QLabel(str(default_val))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        layout.addWidget(value_label)
        
        # Connect slider to value label
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        
        # Store references
        container.slider = slider
        container.value_label = value_label
        
        return container
        
    def create_weight_slider(self, min_val, max_val, default_val):
        """Create a scoring weight slider."""
        container = QFrame()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.valueChanged.connect(self.on_config_changed)
        layout.addWidget(slider)
        
        value_label = QLabel(str(default_val))
        value_label.setMinimumWidth(30)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(value_label)
        
        # Connect slider to value label
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        
        # Store references
        container.slider = slider
        container.value_label = value_label
        
        return container
        
    def load_config(self):
        """Load configuration and update UI."""
        try:
            config = self.config_manager.load_config()
            
            # Load color detection parameters
            red_lower1 = config.get('red_hsv_lower1', [0, 120, 70])
            red_upper1 = config.get('red_hsv_upper1', [10, 255, 255])
            red_lower2 = config.get('red_hsv_lower2', [170, 120, 70])
            red_upper2 = config.get('red_hsv_upper2', [180, 255, 255])
            
            self.red_h_lower1.slider.setValue(red_lower1[0])
            self.red_s_lower1.slider.setValue(red_lower1[1])
            self.red_v_lower1.slider.setValue(red_lower1[2])
            self.red_h_upper1.slider.setValue(red_upper1[0])
            self.red_s_upper1.slider.setValue(red_upper1[1])
            self.red_v_upper1.slider.setValue(red_upper1[2])
            
            self.red_h_lower2.slider.setValue(red_lower2[0])
            self.red_s_lower2.slider.setValue(red_lower2[1])
            self.red_v_lower2.slider.setValue(red_lower2[2])
            self.red_h_upper2.slider.setValue(red_upper2[0])
            self.red_s_upper2.slider.setValue(red_upper2[1])
            self.red_v_upper2.slider.setValue(red_upper2[2])
            
            # Load T-side and CT-side colors
            t_lower = config.get('t_orange_hsv_lower', [10, 150, 150])
            t_upper = config.get('t_orange_hsv_upper', [25, 255, 255])
            ct_lower = config.get('ct_blue_hsv_lower', [100, 150, 150])
            ct_upper = config.get('ct_blue_hsv_upper', [130, 255, 255])
            
            self.t_h_lower.slider.setValue(t_lower[0])
            self.t_s_lower.slider.setValue(t_lower[1])
            self.t_v_lower.slider.setValue(t_lower[2])
            self.t_h_upper.slider.setValue(t_upper[0])
            self.t_s_upper.slider.setValue(t_upper[1])
            self.t_v_upper.slider.setValue(t_upper[2])
            
            self.ct_h_lower.slider.setValue(ct_lower[0])
            self.ct_s_lower.slider.setValue(ct_lower[1])
            self.ct_v_lower.slider.setValue(ct_lower[2])
            self.ct_h_upper.slider.setValue(ct_upper[0])
            self.ct_s_upper.slider.setValue(ct_upper[1])
            self.ct_v_upper.slider.setValue(ct_upper[2])
            
            # Load shape detection parameters
            self.min_height.setValue(config.get('killfeed_rect_min_height', 25))
            self.max_height.setValue(config.get('killfeed_rect_max_height', 50))
            self.min_aspect_ratio.setValue(config.get('killfeed_rect_min_aspect_ratio', 8.0))
            
            # Load timing parameters
            self.kill_memory_duration.setValue(config.get('kill_memory_duration_seconds', 7.0))
            self.ocr_frame_step.setValue(config.get('ocr_frame_step', 30))
            self.pre_buffer.setValue(config.get('clip_pre_buffer_seconds', 7.0))
            self.post_buffer.setValue(config.get('clip_post_buffer_seconds', 8.0))
            
            # Load scoring weights
            scoring_weights = config.get('scoring_weights', {})
            self.kill_weight.slider.setValue(scoring_weights.get('kill', 10))
            self.multi_kill_bonus.slider.setValue(scoring_weights.get('multi_kill_bonus', 15))
            self.team_hype_voice.slider.setValue(scoring_weights.get('team_hype_voice', 20))
            self.enemy_rage_chat.slider.setValue(scoring_weights.get('enemy_rage_chat', 25))
            self.audio_spike.slider.setValue(scoring_weights.get('audio_spike', 5))
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load advanced settings: {str(e)}")
            
    def save_settings(self):
        """Save current settings to configuration."""
        try:
            config = self.config_manager.load_config()
            
            # Save color detection parameters
            config['red_hsv_lower1'] = [
                self.red_h_lower1.slider.value(),
                self.red_s_lower1.slider.value(),
                self.red_v_lower1.slider.value()
            ]
            config['red_hsv_upper1'] = [
                self.red_h_upper1.slider.value(),
                self.red_s_upper1.slider.value(),
                self.red_v_upper1.slider.value()
            ]
            config['red_hsv_lower2'] = [
                self.red_h_lower2.slider.value(),
                self.red_s_lower2.slider.value(),
                self.red_v_lower2.slider.value()
            ]
            config['red_hsv_upper2'] = [
                self.red_h_upper2.slider.value(),
                self.red_s_upper2.slider.value(),
                self.red_v_upper2.slider.value()
            ]
            
            # Save T-side and CT-side colors
            config['t_orange_hsv_lower'] = [
                self.t_h_lower.slider.value(),
                self.t_s_lower.slider.value(),
                self.t_v_lower.slider.value()
            ]
            config['t_orange_hsv_upper'] = [
                self.t_h_upper.slider.value(),
                self.t_s_upper.slider.value(),
                self.t_v_upper.slider.value()
            ]
            config['ct_blue_hsv_lower'] = [
                self.ct_h_lower.slider.value(),
                self.ct_s_lower.slider.value(),
                self.ct_v_lower.slider.value()
            ]
            config['ct_blue_hsv_upper'] = [
                self.ct_h_upper.slider.value(),
                self.ct_s_upper.slider.value(),
                self.ct_v_upper.slider.value()
            ]
            
            # Save shape detection parameters
            config['killfeed_rect_min_height'] = self.min_height.value()
            config['killfeed_rect_max_height'] = self.max_height.value()
            config['killfeed_rect_min_aspect_ratio'] = self.min_aspect_ratio.value()
            
            # Save timing parameters
            config['kill_memory_duration_seconds'] = self.kill_memory_duration.value()
            config['ocr_frame_step'] = self.ocr_frame_step.value()
            config['clip_pre_buffer_seconds'] = self.pre_buffer.value()
            config['clip_post_buffer_seconds'] = self.post_buffer.value()
            
            # Save scoring weights
            config['scoring_weights'] = {
                'kill': self.kill_weight.slider.value(),
                'multi_kill_bonus': self.multi_kill_bonus.slider.value(),
                'team_hype_voice': self.team_hype_voice.slider.value(),
                'enemy_rage_chat': self.enemy_rage_chat.slider.value(),
                'audio_spike': self.audio_spike.slider.value()
            }
            
            # Save configuration
            if self.config_manager.save_config(config):
                QMessageBox.information(self, "Success", "Advanced settings saved successfully!")
                self.config_changed.emit(config)
            else:
                QMessageBox.warning(self, "Error", "Failed to save advanced settings.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save advanced settings: {str(e)}")
            
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self, 
            "Reset to Defaults", 
            "Are you sure you want to reset all advanced settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                default_config = self.config_manager.reset_to_defaults()
                self.load_config()
                QMessageBox.information(self, "Reset Complete", "Advanced settings have been reset to defaults.")
            except Exception as e:
                QMessageBox.critical(self, "Reset Error", f"Failed to reset settings: {str(e)}")
                
    def test_settings(self):
        """Test current settings."""
        QMessageBox.information(self, "Test Settings", "Settings testing will be implemented in future versions.")
        
    def on_config_changed(self):
        """Handle configuration changes."""
        # This could be used to show unsaved changes indicator
        pass
