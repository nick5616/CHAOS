"""
Main window for the CHAOS desktop application.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QStatusBar, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QPushButton, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.utils.theme_manager import ThemeManager


class _CudaCheckThread(QThread):
    result = pyqtSignal(str, str)  # display text, css colour

    def run(self) -> None:
        try:
            import torch
            if torch.cuda.is_available():
                txt = f"CUDA  {torch.cuda.get_device_name(0)}"
                col = "#22c55e"
            else:
                txt = "CPU only"
                col = "#6b7280"
        except Exception:
            txt = ""
            col = ""
        self.result.emit(txt, col)


class ChaosMainWindow(QMainWindow):
    """Main application window — slim nav bar + stacked Home / Results views."""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.theme_manager = ThemeManager()

        self._clip_source_view = None
        self._run_view = None
        self._results_view = None
        self._watch_view = None
        self._settings_modal = None

        self._init_ui()
        self._load_config()
        self._apply_theme()
        self._check_setup_status()

        self._cuda_thread = _CudaCheckThread(self)
        self._cuda_thread.result.connect(self._on_cuda_checked)
        self._cuda_thread.start()

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

        self._clip_source_btn = self._make_nav_button("Clip Source", active=True)
        self._clip_source_btn.clicked.connect(lambda: self._switch_view(0))
        nav_layout.addWidget(self._clip_source_btn)

        self._run_btn = self._make_nav_button("Run", active=False)
        self._run_btn.clicked.connect(lambda: self._switch_view(1))
        nav_layout.addWidget(self._run_btn)

        self._results_btn = self._make_nav_button("Results", active=False)
        self._results_btn.clicked.connect(lambda: self._switch_view(2))
        nav_layout.addWidget(self._results_btn)

        self._watch_btn = self._make_nav_button("Watch", active=False)
        self._watch_btn.clicked.connect(lambda: self._switch_view(3))
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

        # Bottom wizard bar — Back / Next at right
        wizard_bar = QFrame()
        wizard_bar.setFixedHeight(44)
        wizard_bar.setStyleSheet(
            "QFrame { background-color: #1a1d23; border-top: 1px solid #2a2d35; }"
        )
        wiz_layout = QHBoxLayout(wizard_bar)
        wiz_layout.setContentsMargins(16, 0, 16, 0)
        wiz_layout.setSpacing(8)

        self._cuda_lbl = QLabel("")
        self._cuda_lbl.setStyleSheet("color: #6b7280; font-size: 10px; background: transparent;")
        wiz_layout.addWidget(self._cuda_lbl)

        wiz_layout.addStretch()

        self._back_btn = QPushButton("← Back")
        self._back_btn.setObjectName("navButton")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._nav_back)
        wiz_layout.addWidget(self._back_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("navButton")
        self._next_btn.clicked.connect(self._nav_next)
        wiz_layout.addWidget(self._next_btn)

        root.addWidget(wizard_bar)

    def _make_nav_button(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("navButton")
        btn.setProperty("active", "true" if active else "false")
        btn.setCheckable(False)
        return btn

    # ------------------------------------------------------------------ views

    def _ensure_views_loaded(self):
        """Lazy-load views so imports don't block the splash / wizard."""
        if self._clip_source_view is not None:
            return

        from desktop_app.gui.views.home_view import ClipSourceView, RunView
        from desktop_app.gui.views.results_view import ResultsView
        from desktop_app.gui.views.watch_view import WatchView

        self._clip_source_view = ClipSourceView(self.config_manager)
        self._run_view = RunView(self._clip_source_view, self.config_manager)
        self._run_view.pipeline_finished.connect(self._on_pipeline_finished)
        self._results_view = ResultsView(self.config_manager)
        self._watch_view = WatchView(self.config_manager)

        self._stack.addWidget(self._clip_source_view)  # index 0
        self._stack.addWidget(self._run_view)           # index 1
        self._stack.addWidget(self._results_view)       # index 2
        self._stack.addWidget(self._watch_view)         # index 3

    def _switch_view(self, index: int):
        self._ensure_views_loaded()
        self._stack.setCurrentIndex(index)

        for btn, idx in (
            (self._clip_source_btn, 0),
            (self._run_btn, 1),
            (self._results_btn, 2),
            (self._watch_btn, 3),
        ):
            btn.setProperty("active", "true" if index == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._back_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < 3)

        if index == 2 and self._results_view:
            self._results_view.load_results()
        if index == 3 and self._watch_view:
            self._watch_view.load_clips()

    def _nav_back(self):
        idx = self._stack.currentIndex()
        if idx > 0:
            self._switch_view(idx - 1)

    def _nav_next(self):
        idx = self._stack.currentIndex()
        if idx < 3:
            self._switch_view(idx + 1)

    def _on_pipeline_finished(self, success: bool, input_bytes: int):
        if success:
            self._ensure_views_loaded()
            self._results_view.set_input_size(input_bytes)
            self._watch_view.mark_dirty()   # new clips available; reload on next visit
            self._switch_view(2)

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

        except Exception as e:
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
        if self._clip_source_view:
            self._clip_source_view.reload_config()

    # ------------------------------------------------------------------ helpers

    def _on_cuda_checked(self, txt: str, col: str) -> None:
        if txt:
            self._cuda_lbl.setText(txt)
            self._cuda_lbl.setStyleSheet(
                f"color: {col}; font-size: 10px; background: transparent;"
            )

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
