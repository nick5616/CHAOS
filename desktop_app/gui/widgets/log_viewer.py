"""
Log viewer widget for real-time log output.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QLabel, QCheckBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat
from datetime import datetime


class LogViewer(QWidget):
    """Widget for displaying real-time log messages."""
    
    def __init__(self):
        super().__init__()
        self.log_messages = []
        self.max_messages = 1000  # Keep last 1000 messages
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel("📋 Pipeline Log")
        self.title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        header_layout.addWidget(self.auto_scroll_cb)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(self.clear_btn)
        
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_log)
        header_layout.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #444;
            }
        """)
        
        layout.addWidget(self.log_display)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def add_message(self, message: str, level: str = "info"):
        """Add a log message to the display.
        
        Args:
            message: The log message
            level: Log level (info, warning, error, success)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message with timestamp
        formatted_message = f"[{timestamp}] {message}"
        
        # Store message
        self.log_messages.append({
            'timestamp': timestamp,
            'message': message,
            'level': level,
            'formatted': formatted_message
        })
        
        # Keep only last max_messages
        if len(self.log_messages) > self.max_messages:
            self.log_messages.pop(0)
        
        # Add to display
        self.append_to_display(formatted_message, level)
        
        # Update status
        self.status_label.setText(f"Last message: {timestamp}")
        
    def append_to_display(self, message: str, level: str):
        """Append message to the text display with appropriate formatting."""
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Set text format based on level
        format = QTextCharFormat()
        
        if level == "error":
            format.setForeground(QColor("#ff6b6b"))  # Red
        elif level == "warning":
            format.setForeground(QColor("#ffd93d"))  # Yellow
        elif level == "success":
            format.setForeground(QColor("#6bcf7f"))  # Green
        elif level == "info":
            format.setForeground(QColor("#74c0fc"))  # Blue
        else:
            format.setForeground(QColor("#ffffff"))  # White
        
        cursor.setCharFormat(format)
        cursor.insertText(message + "\n")
        
        # Auto-scroll if enabled
        if self.auto_scroll_cb.isChecked():
            self.log_display.setTextCursor(cursor)
            self.log_display.ensureCursorVisible()
    
    def clear_log(self):
        """Clear all log messages."""
        self.log_display.clear()
        self.log_messages.clear()
        self.status_label.setText("Log cleared")
        
    def export_log(self):
        """Export log to file."""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Log",
            f"chaos_pipeline_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("CHAOS Pipeline Log\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for log_entry in self.log_messages:
                        f.write(f"[{log_entry['timestamp']}] [{log_entry['level'].upper()}] {log_entry['message']}\n")
                
                self.add_message(f"Log exported to {file_path}", "success")
                
            except Exception as e:
                self.add_message(f"Failed to export log: {str(e)}", "error")
    
    def get_log_count(self) -> int:
        """Get the number of log messages."""
        return len(self.log_messages)
    
    def get_recent_messages(self, count: int = 10) -> list:
        """Get the most recent log messages."""
        return self.log_messages[-count:] if self.log_messages else []
    
    def filter_messages(self, level: str = None) -> list:
        """Filter messages by level."""
        if level is None:
            return self.log_messages
        return [msg for msg in self.log_messages if msg['level'] == level]
    
    def search_messages(self, query: str) -> list:
        """Search messages containing the query."""
        query_lower = query.lower()
        return [msg for msg in self.log_messages if query_lower in msg['message'].lower()]
