"""
First-run wizard for CHAOS — guides new users through deps, folder, names, and ROI.
"""

from PyQt6.QtWidgets import (
    QDialog, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QProgressBar,
    QFileDialog, QRadioButton, QButtonGroup, QSpinBox, QGroupBox,
    QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.tabs.setup_tab import SetupWorker


# Approximate killfeed and chat ROI presets for common CS2 resolutions.
# Killfeed is in the top-right of the HUD; chat is in the bottom-left.
RESOLUTION_PRESETS = [
    {
        "label": "1920 × 1080  (Full HD)",
        "killfeed_roi": [1478, 30, 1900, 250],
        "chat_roi": [15, 840, 490, 1010],
        "resolution": [1920, 1080],
    },
    {
        "label": "2560 × 1440  (QHD / 1440p)",
        "killfeed_roi": [1978, 40, 2540, 333],
        "chat_roi": [20, 1120, 655, 1345],
        "resolution": [2560, 1440],
    },
    {
        "label": "3440 × 1440  (Ultrawide)",
        "killfeed_roi": [2618, 40, 3420, 333],
        "chat_roi": [20, 1120, 655, 1345],
        "resolution": [3440, 1440],
    },
    {
        "label": "2560 × 1080  (Ultrawide FHD)",
        "killfeed_roi": [2010, 30, 2540, 250],
        "chat_roi": [15, 840, 490, 1010],
        "resolution": [2560, 1080],
    },
]


class FirstRunWizard(QDialog):
    """Blocking setup wizard shown before the main window on first launch."""

    TOTAL_PAGES = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.current_page = 0
        self.setup_done = False

        self._folder_path = ""
        self._player_names = []
        self._killfeed_roi = RESOLUTION_PRESETS[0]["killfeed_roi"][:]
        self._chat_roi = RESOLUTION_PRESETS[0]["chat_roi"][:]
        self._killfeed_roi_resolution = RESOLUTION_PRESETS[0]["resolution"][:]

        self.setWindowTitle("CHAOS Setup")
        self.setFixedSize(680, 520)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)

        self._build_ui()
        self._goto_page(0)

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        # ID selectors: a bare rule would also give every child label the border
        self._header = QFrame()
        self._header.setObjectName("wizardHeader")
        self._header.setFixedHeight(56)
        self._header.setStyleSheet(
            "#wizardHeader { background-color: #1a1d23; border-bottom: 1px solid #2a2d35; }")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("CHAOS")
        logo.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        logo.setStyleSheet("color: #e8963c; background: transparent;")
        header_layout.addWidget(logo)

        header_layout.addStretch()

        self._step_label = QLabel("Step 1 of 4")
        self._step_label.setStyleSheet("color: #6b7280; background: transparent; font-size: 12px;")
        header_layout.addWidget(self._step_label)

        root.addWidget(self._header)

        # Page stack
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page_deps())       # 0
        self._stack.addWidget(self._build_page_folder())     # 1
        self._stack.addWidget(self._build_page_names())      # 2
        self._stack.addWidget(self._build_page_resolution()) # 3
        root.addWidget(self._stack, 1)

        # Footer bar
        footer = QFrame()
        footer.setObjectName("wizardFooter")
        footer.setFixedHeight(64)
        footer.setStyleSheet(
            "#wizardFooter { background-color: #1a1d23; border-top: 1px solid #2a2d35; }")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)

        self._back_btn = QPushButton("← Back")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._go_back)
        footer_layout.addWidget(self._back_btn)

        footer_layout.addStretch()

        # Progress dots
        self._dots_layout = QHBoxLayout()
        self._dots_layout.setSpacing(8)
        self._dot_labels = []
        for _ in range(self.TOTAL_PAGES):
            dot = QLabel("●")
            dot.setStyleSheet("color: #2a2d35; font-size: 10px; background: transparent;")
            self._dots_layout.addWidget(dot)
            self._dot_labels.append(dot)
        footer_layout.addLayout(self._dots_layout)

        footer_layout.addStretch()

        self._next_btn = QPushButton("Next →")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._go_next)
        footer_layout.addWidget(self._next_btn)

        root.addWidget(footer)

    # --------------------------------------------------------- page builders

    def _build_page_deps(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Installing dependencies")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "CHAOS needs FFmpeg and a few Python packages to analyze your footage.\n"
            "This only runs once. Sit tight while we get everything ready."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6b7280;")
        layout.addWidget(desc)

        self._setup_progress = QProgressBar()
        self._setup_progress.setRange(0, 100)
        self._setup_progress.setValue(0)
        layout.addWidget(self._setup_progress)

        self._setup_status = QLabel("Starting…")
        self._setup_status.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(self._setup_status)

        self._setup_log = QTextEdit()
        self._setup_log.setReadOnly(True)
        self._setup_log.setMaximumHeight(180)
        self._setup_log.setPlaceholderText("Setup output will appear here…")
        layout.addWidget(self._setup_log)

        self._gpu_banner = QFrame()
        self._gpu_banner.setStyleSheet(
            "QFrame { background: #2a1f0f; border: 1px solid #e8963c; border-radius: 4px; }"
        )
        gpu_banner_layout = QHBoxLayout(self._gpu_banner)
        gpu_banner_layout.setContentsMargins(12, 8, 12, 8)
        self._gpu_banner_lbl = QLabel("")
        self._gpu_banner_lbl.setWordWrap(True)
        self._gpu_banner_lbl.setStyleSheet("color: #e8963c; font-size: 12px; background: transparent;")
        gpu_banner_layout.addWidget(self._gpu_banner_lbl, 1)
        self._gpu_banner_btn = QPushButton("Enable CUDA…")
        self._gpu_banner_btn.clicked.connect(self._show_gpu_dialog)
        gpu_banner_layout.addWidget(self._gpu_banner_btn)
        self._gpu_banner.setVisible(False)
        layout.addWidget(self._gpu_banner)

        layout.addStretch()
        return page

    def _build_page_folder(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Where are your CS2 clips?")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("Point CHAOS to the folder where your CS2 recordings are saved.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6b7280;")
        layout.addWidget(desc)

        row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g.  D:\\Videos\\CS2  or  ~/Movies/CS2")
        self._folder_edit.textChanged.connect(self._validate_folder_page)
        row.addWidget(self._folder_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_folder)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self._folder_error = QLabel("")
        self._folder_error.setProperty("class", "error")
        self._folder_error.setStyleSheet("color: #f87171; font-size: 12px;")
        layout.addWidget(self._folder_error)

        layout.addStretch()
        return page

    def _build_page_names(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("What are your in-game name(s)? (optional)")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "CHAOS works out your name from each video's killfeed, so you can leave this empty.\n"
            "Names here only help with short clips that show too few of your kills and deaths to tell. "
            "One name per line."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6b7280;")
        layout.addWidget(desc)

        self._names_edit = QTextEdit()
        self._names_edit.setPlaceholderText("nickb\nalternateName\n...")
        self._names_edit.setMaximumHeight(140)
        self._names_edit.textChanged.connect(self._validate_names_page)
        layout.addWidget(self._names_edit)

        layout.addStretch()
        return page

    def _build_page_resolution(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)

        title = QLabel("What resolution do you play at?")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "This sets the killfeed detection region. Choose your in-game resolution."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6b7280;")
        layout.addWidget(desc)

        self._res_group = QButtonGroup(self)
        self._res_radios = []
        for i, preset in enumerate(RESOLUTION_PRESETS):
            rb = QRadioButton(preset["label"])
            if i == 0:
                rb.setChecked(True)
            rb.toggled.connect(lambda checked, idx=i: self._on_preset_selected(idx) if checked else None)
            self._res_group.addButton(rb, i)
            self._res_radios.append(rb)
            layout.addWidget(rb)

        custom_rb = QRadioButton("Custom coordinates")
        custom_rb.toggled.connect(self._on_custom_toggled)
        self._res_group.addButton(custom_rb, len(RESOLUTION_PRESETS))
        self._res_radios.append(custom_rb)
        layout.addWidget(custom_rb)

        # Custom spinbox panel (hidden by default)
        self._custom_box = QGroupBox("Custom ROI coordinates  (x1, y1, x2, y2)")
        custom_layout = QVBoxLayout(self._custom_box)

        kf_row = QHBoxLayout()
        kf_row.addWidget(QLabel("Killfeed:"))
        self._kf_spins = []
        for _ in range(4):
            sp = QSpinBox()
            sp.setRange(0, 9999)
            sp.setMinimumHeight(30)
            sp.valueChanged.connect(self._read_custom_rois)
            kf_row.addWidget(sp)
            self._kf_spins.append(sp)
        custom_layout.addLayout(kf_row)

        chat_row = QHBoxLayout()
        chat_row.addWidget(QLabel("Chat:     "))
        self._chat_spins = []
        for _ in range(4):
            sp = QSpinBox()
            sp.setRange(0, 9999)
            sp.setMinimumHeight(30)
            sp.valueChanged.connect(self._read_custom_rois)
            chat_row.addWidget(sp)
            self._chat_spins.append(sp)
        custom_layout.addLayout(chat_row)

        self._custom_box.setVisible(False)
        layout.addWidget(self._custom_box)

        note = QLabel("These regions are approximate. Check them with a test run on your footage.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout.addWidget(note)

        layout.addStretch()
        return page

    # -------------------------------------------------------- navigation

    def _goto_page(self, index: int):
        self.current_page = index
        self._stack.setCurrentIndex(index)
        self._step_label.setText(f"Step {index + 1} of {self.TOTAL_PAGES}")

        # Update dots
        for i, dot in enumerate(self._dot_labels):
            if i < index:
                dot.setStyleSheet("color: #4ade80; font-size: 10px; background: transparent;")
            elif i == index:
                dot.setStyleSheet("color: #e8963c; font-size: 10px; background: transparent;")
            else:
                dot.setStyleSheet("color: #2a2d35; font-size: 10px; background: transparent;")

        self._back_btn.setEnabled(index > 0)

        if index == self.TOTAL_PAGES - 1:
            self._next_btn.setText("Finish")
        else:
            self._next_btn.setText("Next →")

        # Page-specific on-enter actions
        if index == 0:
            self._start_setup()
            self._next_btn.setEnabled(False)
        elif index == 1:
            self._validate_folder_page()
        elif index == 2:
            self._validate_names_page()
        elif index == 3:
            self._next_btn.setEnabled(True)

    def _go_next(self):
        if self.current_page < self.TOTAL_PAGES - 1:
            self._goto_page(self.current_page + 1)
        else:
            self._finish()

    def _go_back(self):
        if self.current_page > 0:
            self._goto_page(self.current_page - 1)

    # -------------------------------------------------------- setup page

    def _start_setup(self):
        self._setup_log.clear()
        self._setup_status.setText("Starting setup…")
        self._setup_progress.setValue(0)

        self._gpu_info = {}
        self._gpu_banner.setVisible(False)

        self._worker = SetupWorker(install_ffmpeg=True, install_dependencies=True)
        self._worker.progress_updated.connect(self._on_setup_progress)
        self._worker.step_completed.connect(self._on_setup_step)
        self._worker.gpu_info.connect(self._on_gpu_info)
        self._worker.finished.connect(self._on_setup_finished)
        self._worker.start()

    def _on_setup_progress(self, pct: int, msg: str):
        self._setup_progress.setValue(pct)
        self._setup_status.setText(msg)

    def _on_setup_step(self, name: str, ok: bool):
        mark = ("<span style='color:#4ade80'>✓</span>" if ok
                else "<span style='color:#f87171'>✗</span>")
        self._setup_log.append(f"{mark}&nbsp;&nbsp;{name}")

    def _on_gpu_info(self, info: dict):
        self._gpu_info = info
        if info.get('gpu_present') and not info.get('available'):
            name = info.get('gpu_name') or 'Your GPU'
            self._gpu_banner_lbl.setText(
                f"{name} detected. Enable CUDA for up to 8x faster analysis."
            )
            self._gpu_banner.setVisible(True)

    def _show_gpu_dialog(self):
        from desktop_app.gui.views.home_view import _HardwareInfoDialog

        system = {
            'cuda_available': self._gpu_info.get('available', False),
            'gpu_present': self._gpu_info.get('gpu_present', False),
            'gpu_name': self._gpu_info.get('gpu_name'),
            'nvidia_driver_version': self._gpu_info.get('driver_version'),
            'nvidia_max_cuda_version': self._gpu_info.get('max_cuda_version'),
        }
        _HardwareInfoDialog(system, self).exec()

    def _on_setup_finished(self, success: bool):
        self.setup_done = True
        if success:
            self._setup_status.setText("Setup complete. You're good to go!")
            self._setup_log.append("\nAll dependencies are ready.")
        else:
            self._setup_status.setText("Setup finished with warnings. Some items may be missing.")
            self._setup_log.append("\nProceed anyway, or re-run setup from Settings later.")
        self._next_btn.setEnabled(True)

    # -------------------------------------------------------- folder page

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select CS2 clips folder")
        if path:
            self._folder_edit.setText(path)

    def _validate_folder_page(self):
        text = self._folder_edit.text().strip()
        if text:
            self._folder_path = text
            self._folder_error.setText("")
            self._next_btn.setEnabled(True)
        else:
            self._folder_error.setText("Please select a folder.")
            self._next_btn.setEnabled(False)

    # -------------------------------------------------------- names page

    def _validate_names_page(self):
        raw = self._names_edit.toPlainText()
        self._player_names = [n.strip() for n in raw.splitlines() if n.strip()]
        self._next_btn.setEnabled(True)

    # -------------------------------------------------------- resolution page

    def _on_preset_selected(self, index: int):
        self._killfeed_roi = RESOLUTION_PRESETS[index]["killfeed_roi"][:]
        self._chat_roi = RESOLUTION_PRESETS[index]["chat_roi"][:]
        self._killfeed_roi_resolution = RESOLUTION_PRESETS[index]["resolution"][:]
        self._custom_box.setVisible(False)

    def _on_custom_toggled(self, checked: bool):
        self._custom_box.setVisible(checked)
        if checked:
            self._read_custom_rois()

    def _read_custom_rois(self):
        self._killfeed_roi = [sp.value() for sp in self._kf_spins]
        self._chat_roi = [sp.value() for sp in self._chat_spins]
        # Custom values are entered against the user's own footage, so use
        # them as-is with no resolution-based rescaling.
        self._killfeed_roi_resolution = None

    # -------------------------------------------------------- finish

    def _finish(self):
        config = self.config_manager.load_config()
        config["captures_folder"] = self._folder_path
        config["player_names"] = self._player_names
        config["killfeed_roi"] = self._killfeed_roi
        config["chat_roi"] = self._chat_roi
        config["killfeed_roi_resolution"] = self._killfeed_roi_resolution
        if "gui" not in config:
            config["gui"] = {}
        config["gui"]["setup_complete"] = True
        self.config_manager.save_config(config)
        self.accept()

    # -------------------------------------------------------- close guard

    def closeEvent(self, event):
        if self.current_page < self.TOTAL_PAGES - 1 and not self.result():
            event.ignore()
        else:
            event.accept()

    def reject(self):
        # Only allow dismissal after completing the wizard
        if self.current_page >= self.TOTAL_PAGES - 1:
            super().reject()
