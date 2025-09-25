"""
Theme manager for the CHAOS desktop application.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication


class ThemeManager(QObject):
    """Manages application themes and styling."""
    
    theme_changed = pyqtSignal(str)  # Emits when theme changes
    
    def __init__(self):
        super().__init__()
        self.current_theme = "default"
        self.themes = {
            "default": self.get_default_theme(),
            "dark": self.get_dark_theme(),
            "light": self.get_light_theme()
        }
        
    def get_default_theme(self):
        """Get the default theme stylesheet."""
        return """
        /* Default Theme */
        QMainWindow {
            background-color: #f5f5f5;
        }
        
        QTabWidget::pane {
            border: 1px solid #c0c0c0;
            background-color: white;
        }
        
        QTabBar::tab {
            background-color: #e0e0e0;
            border: 1px solid #c0c0c0;
            padding: 8px 12px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 1px solid white;
        }
        
        QTabBar::tab:hover {
            background-color: #f0f0f0;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #c0c0c0;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        
        QPushButton {
            background-color: #e0e0e0;
            border: 1px solid #c0c0c0;
            border-radius: 3px;
            padding: 5px 10px;
            min-width: 80px;
        }
        
        QPushButton:hover {
            background-color: #f0f0f0;
        }
        
        QPushButton:pressed {
            background-color: #d0d0d0;
        }
        
        QPushButton:disabled {
            background-color: #f5f5f5;
            color: #999999;
        }
        
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            border: 1px solid #c0c0c0;
            border-radius: 3px;
            padding: 3px;
            background-color: white;
        }
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 2px solid #4CAF50;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #c0c0c0;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
        }
        
        QSlider::handle:horizontal {
            background: #4CAF50;
            border: 1px solid #4CAF50;
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #45a049;
        }
        
        QProgressBar {
            border: 2px solid #c0c0c0;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 3px;
        }
        
        QListWidget {
            border: 1px solid #c0c0c0;
            border-radius: 3px;
            background-color: white;
        }
        
        QListWidget::item {
            padding: 5px;
            border-bottom: 1px solid #f0f0f0;
        }
        
        QListWidget::item:selected {
            background-color: #4CAF50;
            color: white;
        }
        
        QListWidget::item:hover {
            background-color: #f0f0f0;
        }
        
        QScrollArea {
            border: 1px solid #c0c0c0;
            border-radius: 3px;
        }
        
        QStatusBar {
            background-color: #e0e0e0;
            border-top: 1px solid #c0c0c0;
        }
        """
        
    def get_dark_theme(self):
        """Get the dark theme stylesheet."""
        return """
        /* Dark Theme */
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        
        QTabWidget::pane {
            border: 1px solid #555555;
            background-color: #3c3c3c;
        }
        
        QTabBar::tab {
            background-color: #404040;
            border: 1px solid #555555;
            color: #ffffff;
            padding: 8px 12px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #3c3c3c;
            border-bottom: 1px solid #3c3c3c;
        }
        
        QTabBar::tab:hover {
            background-color: #4a4a4a;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #555555;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            color: #ffffff;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        
        QPushButton {
            background-color: #404040;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 5px 10px;
            min-width: 80px;
            color: #ffffff;
        }
        
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        
        QPushButton:pressed {
            background-color: #353535;
        }
        
        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #666666;
        }
        
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 3px;
            background-color: #3c3c3c;
            color: #ffffff;
        }
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 2px solid #4CAF50;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #555555;
            height: 8px;
            background: #404040;
            border-radius: 4px;
        }
        
        QSlider::handle:horizontal {
            background: #4CAF50;
            border: 1px solid #4CAF50;
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #45a049;
        }
        
        QProgressBar {
            border: 2px solid #555555;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
            color: #ffffff;
        }
        
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 3px;
        }
        
        QListWidget {
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #3c3c3c;
            color: #ffffff;
        }
        
        QListWidget::item {
            padding: 5px;
            border-bottom: 1px solid #4a4a4a;
        }
        
        QListWidget::item:selected {
            background-color: #4CAF50;
            color: white;
        }
        
        QListWidget::item:hover {
            background-color: #4a4a4a;
        }
        
        QScrollArea {
            border: 1px solid #555555;
            border-radius: 3px;
        }
        
        QStatusBar {
            background-color: #404040;
            border-top: 1px solid #555555;
            color: #ffffff;
        }
        """
        
    def get_light_theme(self):
        """Get the light theme stylesheet."""
        return """
        /* Light Theme */
        QMainWindow {
            background-color: #ffffff;
        }
        
        QTabWidget::pane {
            border: 1px solid #d0d0d0;
            background-color: #fafafa;
        }
        
        QTabBar::tab {
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
            padding: 8px 12px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #fafafa;
            border-bottom: 1px solid #fafafa;
        }
        
        QTabBar::tab:hover {
            background-color: #f5f5f5;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #d0d0d0;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 5px 10px;
            min-width: 80px;
        }
        
        QPushButton:hover {
            background-color: #f5f5f5;
        }
        
        QPushButton:pressed {
            background-color: #e8e8e8;
        }
        
        QPushButton:disabled {
            background-color: #f8f8f8;
            color: #aaaaaa;
        }
        
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 3px;
            background-color: #ffffff;
        }
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 2px solid #4CAF50;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #d0d0d0;
            height: 8px;
            background: #f0f0f0;
            border-radius: 4px;
        }
        
        QSlider::handle:horizontal {
            background: #4CAF50;
            border: 1px solid #4CAF50;
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #45a049;
        }
        
        QProgressBar {
            border: 2px solid #d0d0d0;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 3px;
        }
        
        QListWidget {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            background-color: #ffffff;
        }
        
        QListWidget::item {
            padding: 5px;
            border-bottom: 1px solid #f5f5f5;
        }
        
        QListWidget::item:selected {
            background-color: #4CAF50;
            color: white;
        }
        
        QListWidget::item:hover {
            background-color: #f5f5f5;
        }
        
        QScrollArea {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
        }
        
        QStatusBar {
            background-color: #f0f0f0;
            border-top: 1px solid #d0d0d0;
        }
        """
        
    def apply_theme(self, theme_name: str):
        """Apply a theme to the application."""
        if theme_name not in self.themes:
            theme_name = "default"
            
        self.current_theme = theme_name
        
        app = QApplication.instance()
        if app:
            if theme_name == "default":
                # For default theme, use system styling (no custom stylesheet)
                app.setStyleSheet("")
                # Apply system palette for proper dark mode support
                self.apply_system_palette()
            else:
                # Apply custom theme stylesheet
                stylesheet = self.themes[theme_name]
                app.setStyleSheet(stylesheet)
            
        self.theme_changed.emit(theme_name)
        
    def apply_system_palette(self):
        """Apply system palette for proper dark mode support."""
        app = QApplication.instance()
        if app:
            # Let the system handle the palette automatically
            # This ensures proper dark mode support on macOS and other systems
            app.setPalette(QApplication.style().standardPalette())
        
    def get_available_themes(self):
        """Get list of available themes."""
        return list(self.themes.keys())
        
    def get_current_theme(self):
        """Get the current theme name."""
        return self.current_theme
