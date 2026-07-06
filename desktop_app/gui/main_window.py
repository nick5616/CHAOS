"""
Main window for the CHAOS desktop application.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QStatusBar, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QPushButton, QDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.utils.theme_manager import ThemeManager


class ChaosMainWindow(QMainWindow):
    """Main application window — slim nav bar + stacked Home / Results views."""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.theme_manager = ThemeManager()

        self._home_view = None
        self._results_view = None
        self._watch_view = None
        self._settings_modal = None

        self._init_ui()
        self._load_config()
        self._apply_theme()
        self._check_setup_status()

    # ------------------------------------------------------------------ build

    def _init_ui(self):
        self.setWindowTitle("CHAOS")
        self.setGeometry(100, 100, 1200, 800)

        icon_path = Path(__file__).parent.parent / "resources" / "icons" / "chaos_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top nav bar
        nav_bar = QFrame()
        nav_bar.setFixedHeight(48)
        nav_bar.setStyleSheet(
            "QFrame { background-color: #1a1d23; border-bottom: 1px solid #2a2d35; }"
        )
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(16, 0, 12, 0)
        nav_layout.setSpacing(4)

        logo = QLabel("CHAOS")
        logo.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        logo.setStyleSheet("color: #e8963c; background: transparent; padding-right: 16px;")
        nav_layout.addWidget(logo)

        self._home_btn = self._make_nav_button("Home", active=True)
        self._home_btn.clicked.connect(lambda: self._switch_view(0))
        nav_layout.addWidget(self._home_btn)

        self._results_btn = self._make_nav_button("Results", active=False)
        self._results_btn.clicked.connect(lambda: self._switch_view(1))
        nav_layout.addWidget(self._results_btn)

        self._watch_btn = self._make_nav_button("Watch", active=False)
        self._watch_btn.clicked.connect(lambda: self._switch_view(2))
        nav_layout.addWidget(self._watch_btn)

        nav_layout.addStretch()

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("settingsButton")
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setFixedSize(36, 36)
        self._settings_btn.clicked.connect(self._open_settings)
        nav_layout.addWidget(self._settings_btn)

        root.addWidget(nav_bar)

        # View stack — populated lazily after first shown to avoid slow imports at startup
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #6b7280;")
        self._status_bar.addWidget(self._status_label)

    def _make_nav_button(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("navButton")
        btn.setProperty("active", "true" if active else "false")
        btn.setCheckable(False)
        return btn

    # ------------------------------------------------------------------ views

    def _ensure_views_loaded(self):
        """Lazy-load views so imports don't block the splash / wizard."""
        if self._home_view is not None:
            return

        from desktop_app.gui.views.home_view import HomeView
        from desktop_app.gui.views.results_view import ResultsView
        from desktop_app.gui.views.watch_view import WatchView

        self._home_view = HomeView(self.config_manager)
        self._home_view.pipeline_finished.connect(self._on_pipeline_finished)
        self._results_view = ResultsView(self.config_manager)
        self._watch_view = WatchView(self.config_manager)

        self._stack.addWidget(self._home_view)     # index 0
        self._stack.addWidget(self._results_view)  # index 1
        self._stack.addWidget(self._watch_view)    # index 2

    def _switch_view(self, index: int):
        self._ensure_views_loaded()
        self._stack.setCurrentIndex(index)

        for btn, idx in (
            (self._home_btn, 0),
            (self._results_btn, 1),
            (self._watch_btn, 2),
        ):
            btn.setProperty("active", "true" if index == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if index == 1 and self._results_view:
            self._results_view.load_results()
        if index == 2 and self._watch_view:
            self._watch_view.load_clips()

    def _on_pipeline_finished(self, success: bool, input_bytes: int):
        if success:
            self._ensure_views_loaded()
            self._results_view.set_input_size(input_bytes)
            self._update_status("Pipeline complete — highlights ready")
            self._switch_view(1)
        else:
            self._update_status("Pipeline finished with errors — check the log")

    # ------------------------------------------------------------------ setup

    def _check_setup_status(self):
        try:
            config = self.config_manager.load_config()
            setup_complete = config.get("gui", {}).get("setup_complete", False)

            if not setup_complete:
                from desktop_app.gui.wizard.first_run_wizard import FirstRunWizard
                wizard = FirstRunWizard(self)
                result = wizard.exec()
                if result != QDialog.DialogCode.Accepted:
                    import sys
                    sys.exit(0)

            self._ensure_views_loaded()
            self._stack.setCurrentIndex(0)
            self._update_status("Ready")

        except Exception as e:
            self._update_status(f"Error during startup: {e}")
            self._ensure_views_loaded()

    # ------------------------------------------------------------------ config / theme

    def _load_config(self):
        try:
            config = self.config_manager.load_config()
            gui_cfg = config.get("gui", {})
            w, h = gui_cfg.get("window_size", [1200, 800])
            self.resize(w, h)
        except Exception:
            pass

    def _apply_theme(self):
        try:
            config = self.config_manager.load_config()
            theme = config.get("gui", {}).get("theme", "cs2")
            self.theme_manager.apply_theme(theme)
        except Exception:
            self.theme_manager.apply_theme("cs2")

    def _open_settings(self):
        from desktop_app.gui.views.settings_modal import SettingsModal
        modal = SettingsModal(self.config_manager, self)
        modal.exec()
        # Reload config in home view in case paths/names changed
        if self._home_view:
            self._home_view.reload_config()

    # ------------------------------------------------------------------ helpers

    def _update_status(self, msg: str):
        self._status_label.setText(msg)

    def closeEvent(self, event):
        try:
            config = self.config_manager.load_config()
            if "gui" not in config:
                config["gui"] = {}
            config["gui"]["window_size"] = [self.width(), self.height()]
            self.config_manager.save_config(config)
        except Exception:
            pass
        event.accept()
