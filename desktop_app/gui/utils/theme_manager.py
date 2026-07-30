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
            "light": self.get_light_theme(),
            "cs2": self.get_cs2_theme()
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
        
    def get_cs2_theme(self):
        """Get the CS2-inspired dark theme stylesheet."""
        return """
        /* CS2 Theme — dark with orange accents */
        * { color: #c8ccd4; }

        QMainWindow, QDialog {
            background-color: #0f1014;
        }

        QWidget {
            background-color: #0f1014;
            color: #c8ccd4;
        }

        QFrame[frameShape="4"], QFrame[frameShape="5"] {
            color: #2a2d35;
        }

        QGroupBox {
            font-weight: bold;
            font-size: 11px;
            letter-spacing: 1px;
            text-transform: uppercase;
            border: none;
            border-top: 1px solid #2a2d35;
            border-radius: 0px;
            margin-top: 18px;
            padding-top: 10px;
            color: #6b7280;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 0px;
            top: -2px;
            padding: 0 0 0 0;
        }

        QPushButton {
            background-color: #1a1d23;
            border: 1px solid #2a2d35;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 80px;
            color: #c8ccd4;
            font-size: 12px;
        }

        QPushButton:hover {
            background-color: #22262e;
            border-color: #e8963c;
            color: #e8963c;
        }

        QPushButton:pressed {
            background-color: #12151a;
        }

        QPushButton:disabled {
            background-color: #12151a;
            border-color: #1e2128;
            color: #3a3d45;
        }

        QPushButton#runButton {
            background-color: #e8963c;
            border: none;
            border-radius: 6px;
            color: #0f1014;
            font-size: 16px;
            font-weight: bold;
            min-height: 52px;
            min-width: 220px;
            letter-spacing: 1px;
        }

        QPushButton#runButton:hover {
            background-color: #d4822a;
            color: #0f1014;
        }

        QPushButton#runButton:pressed {
            background-color: #bf7020;
        }

        QPushButton#runButton:disabled {
            background-color: #2a2d35;
            color: #4a4d55;
        }

        QPushButton#navButton {
            background-color: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            border-radius: 0px;
            padding: 8px 16px;
            color: #6b7280;
            font-size: 13px;
            min-width: 60px;
        }

        QPushButton#navButton:hover {
            color: #c8ccd4;
            border-bottom-color: #2a2d35;
        }

        QPushButton#navButton[active="true"] {
            color: #e8963c;
            border-bottom-color: #e8963c;
        }

        QPushButton#settingsButton {
            background-color: transparent;
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            color: #6b7280;
            font-size: 13px;
            min-width: 0px;
        }

        QPushButton#settingsButton:hover {
            color: #e8963c;
            background-color: #1a1d23;
        }

        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #12151a;
            border: 1px solid #2a2d35;
            border-radius: 4px;
            padding: 5px 8px;
            color: #c8ccd4;
            selection-background-color: #e8963c;
            selection-color: #0f1014;
        }

        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #e8963c;
        }

        QLineEdit[readOnly="true"] {
            color: #6b7280;
        }

        QTextEdit, QPlainTextEdit {
            background-color: #12151a;
            border: 1px solid #2a2d35;
            border-radius: 4px;
            padding: 4px;
            color: #c8ccd4;
            selection-background-color: #e8963c;
            selection-color: #0f1014;
        }

        QTextEdit:focus, QPlainTextEdit:focus {
            border-color: #e8963c;
        }

        QProgressBar {
            background-color: #1a1d23;
            border: 1px solid #2a2d35;
            border-radius: 4px;
            text-align: center;
            color: #c8ccd4;
            font-size: 11px;
            min-height: 14px;
        }

        QProgressBar::chunk {
            background-color: #e8963c;
            border-radius: 3px;
        }

        QListWidget {
            background-color: #12151a;
            border: 1px solid #2a2d35;
            border-radius: 4px;
            color: #c8ccd4;
            outline: none;
        }

        QListWidget::item {
            padding: 6px 8px;
            border-bottom: 1px solid #1a1d23;
        }

        QListWidget::item:selected {
            background-color: #22262e;
            color: #e8963c;
            border-left: 2px solid #e8963c;
        }

        QListWidget::item:hover {
            background-color: #1a1d23;
        }

        QScrollArea {
            background-color: #0f1014;
            border: 1px solid #2a2d35;
            border-radius: 4px;
        }

        QScrollBar:vertical {
            background-color: #12151a;
            width: 8px;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical {
            background-color: #2a2d35;
            border-radius: 4px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #e8963c;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QScrollBar:horizontal {
            background-color: #12151a;
            height: 8px;
            border-radius: 4px;
        }

        QScrollBar::handle:horizontal {
            background-color: #2a2d35;
            border-radius: 4px;
            min-width: 20px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #e8963c;
        }

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        QSlider::groove:horizontal {
            background-color: #1a1d23;
            border: 1px solid #2a2d35;
            height: 6px;
            border-radius: 3px;
        }

        QSlider::handle:horizontal {
            background-color: #e8963c;
            border: none;
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }

        QSlider::handle:horizontal:hover {
            background-color: #d4822a;
        }

        QSlider::sub-page:horizontal {
            background-color: #e8963c;
            border-radius: 3px;
        }

        QLabel {
            color: #c8ccd4;
            background-color: transparent;
        }

        QLabel[class="dim"] {
            color: #6b7280;
            font-size: 11px;
        }

        QLabel[class="error"] {
            color: #f87171;
        }

        QLabel[class="success"] {
            color: #4ade80;
        }

        QLabel[class="accent"] {
            color: #e8963c;
            font-weight: bold;
        }

        QCheckBox {
            color: #c8ccd4;
            spacing: 8px;
        }

        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #2a2d35;
            border-radius: 3px;
            background-color: #12151a;
        }

        QCheckBox::indicator:checked {
            background-color: #e8963c;
            border-color: #e8963c;
            image: none;
        }

        QCheckBox::indicator:hover {
            border-color: #e8963c;
        }

        QRadioButton {
            color: #c8ccd4;
            spacing: 8px;
        }

        QRadioButton::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #2a2d35;
            border-radius: 8px;
            background-color: #12151a;
        }

        QRadioButton::indicator:checked {
            background-color: #e8963c;
            border-color: #e8963c;
        }

        QRadioButton::indicator:hover {
            border-color: #e8963c;
        }

        QStatusBar {
            background-color: #0a0c10;
            border-top: 1px solid #2a2d35;
            color: #6b7280;
            font-size: 11px;
        }

        QStatusBar QLabel {
            color: #6b7280;
        }

        QSplitter::handle {
            background-color: #2a2d35;
        }

        QSplitter::handle:horizontal {
            width: 1px;
        }

        QSplitter::handle:vertical {
            height: 1px;
        }

        QTabWidget::pane {
            border: 1px solid #2a2d35;
            background-color: #0f1014;
        }

        QTabBar::tab {
            background-color: #12151a;
            border: 1px solid #2a2d35;
            border-bottom: none;
            color: #6b7280;
            padding: 6px 14px;
            margin-right: 2px;
        }

        QTabBar::tab:selected {
            background-color: #0f1014;
            color: #e8963c;
            border-top-color: #e8963c;
        }

        QTabBar::tab:hover {
            color: #c8ccd4;
        }

        QComboBox {
            background-color: #12151a;
            border: 1px solid #2a2d35;
            border-radius: 4px;
            padding: 5px 8px;
            color: #c8ccd4;
            min-width: 80px;
        }

        QComboBox:hover {
            border-color: #e8963c;
        }

        QComboBox::drop-down {
            border: none;
            width: 20px;
        }

        QComboBox QAbstractItemView {
            background-color: #1a1d23;
            border: 1px solid #2a2d35;
            color: #c8ccd4;
            selection-background-color: #22262e;
            selection-color: #e8963c;
        }

        QToolTip {
            background-color: #1a1d23;
            border: 1px solid #2a2d35;
            color: #c8ccd4;
            padding: 4px 8px;
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
                app.setStyleSheet("")
                self.apply_system_palette()
            else:
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
