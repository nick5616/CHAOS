"""
Settings modal — combines general config and advanced detection settings.
Opened from the gear icon in the main window nav bar.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QSpinBox,
    QGroupBox, QFileDialog, QMessageBox, QScrollArea, QFrame, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from desktop_app.gui.utils.config_manager import ConfigManager
from desktop_app.gui.tabs.advanced_tab import AdvancedTab

# (config value, label) for moments.mode, see chaos_lib/moments.py
MOMENT_MODES = [
    ("off", "Off"),
    ("funny", "Funny moments only"),
    ("conversations", "Funny moments + all conversations for review"),
]

# Same resolution presets as the wizard
RESOLUTION_PRESETS = [
    {"label": "1920×1080", "killfeed_roi": [1478, 30, 1900, 250], "chat_roi": [15, 840, 490, 1010], "resolution": [1920, 1080]},
    {"label": "2560×1440", "killfeed_roi": [1978, 40, 2540, 333], "chat_roi": [20, 1120, 655, 1345], "resolution": [2560, 1440]},
    {"label": "3440×1440", "killfeed_roi": [2618, 40, 3420, 333], "chat_roi": [20, 1120, 655, 1345], "resolution": [3440, 1440]},
    {"label": "2560×1080", "killfeed_roi": [2010, 30, 2540, 250], "chat_roi": [15, 840, 490, 1010], "resolution": [2560, 1080]},
]


class SettingsModal(QDialog):
    """Application settings in a tabbed modal dialog."""

    _LABEL_W = 150  # shared width of row labels so the fields line up

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 560)
        self.resize(780, 620)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tabs = QTabWidget()

        # General tab
        general_tab = QWidget()
        self._build_general_tab(general_tab)
        tabs.addTab(general_tab, "General")

        # Advanced tab — reuse existing widget
        self._advanced_tab = AdvancedTab()
        tabs.addTab(self._advanced_tab, "Advanced")

        root.addWidget(tabs, 1)

        # Footer buttons
        footer = QFrame()
        footer.setStyleSheet("QFrame { border-top: 1px solid #2a2d35; background-color: #1a1d23; }")
        footer.setFixedHeight(52)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #e8963c; color: #0f1014; font-weight: bold; "
            "border: none; border-radius: 4px; padding: 6px 20px; }"
            "QPushButton:hover { background-color: #d4822a; }"
        )
        save_btn.clicked.connect(self._save)
        footer_layout.addWidget(save_btn)

        root.addWidget(footer)

    def _build_general_tab(self, parent: QWidget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # Paths
        paths_box = QGroupBox("Paths")
        paths_layout = QVBoxLayout(paths_box)

        self._captures_edit, captures_row = self._make_folder_row("Captures folder:")
        self._data_edit, data_row = self._make_folder_row("Data folder:")
        self._clips_edit, clips_row = self._make_folder_row("Output (clips) folder:")

        paths_layout.addLayout(captures_row)
        paths_layout.addLayout(data_row)
        paths_layout.addLayout(clips_row)
        layout.addWidget(paths_box)

        # Player names
        names_box = QGroupBox("Player names")
        names_layout = QVBoxLayout(names_box)
        hint = QLabel("Optional. Your name is read from each video's killfeed; "
                      "these only help short clips with too few rows to tell. One per line.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        names_layout.addWidget(hint)
        self._names_edit = QTextEdit()
        self._names_edit.setMaximumHeight(100)
        names_layout.addWidget(self._names_edit)
        layout.addWidget(names_box)

        # Killfeed and chat regions
        kf_box = QGroupBox("Screen regions (pixels)")
        kf_layout = QVBoxLayout(kf_box)
        kf_layout.setSpacing(8)

        # Resolution presets
        preset_row = QHBoxLayout()
        preset_lbl = QLabel("Preset:")
        preset_lbl.setFixedWidth(self._LABEL_W)
        preset_row.addWidget(preset_lbl)
        for preset in RESOLUTION_PRESETS:
            btn = QPushButton(preset["label"])
            btn.setStyleSheet("QPushButton { padding: 4px 12px; min-width: 0; }")
            btn.setToolTip("Fill in both regions for this in-game resolution")
            # Capture preset value in closure
            btn.clicked.connect(lambda _, p=preset: self._apply_roi_preset(p))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        kf_layout.addLayout(preset_row)

        self._kf_spins, kf_spin_row = self._make_roi_row("Killfeed")
        kf_layout.addLayout(kf_spin_row)
        self._chat_spins, chat_spin_row = self._make_roi_row("Chat")
        kf_layout.addLayout(chat_spin_row)
        layout.addWidget(kf_box)

        # Voice chat: clips without kills, and subtitles
        voice_box = QGroupBox("Voice chat")
        voice_layout = QVBoxLayout(voice_box)
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Voice-chat moments:")
        mode_lbl.setFixedWidth(self._LABEL_W)
        mode_row.addWidget(mode_lbl)
        self._moments_combo = QComboBox()
        for value, label in MOMENT_MODES:
            self._moments_combo.addItem(label, value)
        mode_row.addWidget(self._moments_combo, 1)
        voice_layout.addLayout(mode_row)
        moments_hint = QLabel("Clips banter and laughter even when nobody got a kill. "
                              "Conversations go to a \"conversations\" folder inside your clips folder, "
                              "best first, for you to skim.")
        moments_hint.setWordWrap(True)
        moments_hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        voice_layout.addWidget(moments_hint)

        self._subs_check = QCheckBox("Add voice-chat subtitles to clips")
        voice_layout.addWidget(self._subs_check)
        subs_hint = QLabel("Burns captions into each clip and saves an .srt next to it "
                           "(upload it to YouTube as closed captions). Clips are re-encoded, "
                           "so clipping takes longer.")
        subs_hint.setWordWrap(True)
        subs_hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        voice_layout.addWidget(subs_hint)
        layout.addWidget(voice_box)

        layout.addStretch()
        scroll.setWidget(content)

        tab_layout = QVBoxLayout(parent)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def _make_roi_row(self, title: str):
        """'Title  x1 [ ]  y1 [ ]  x2 [ ]  y2 [ ]' with each label next to its box."""
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel(f"{title}:")
        lbl.setFixedWidth(self._LABEL_W)
        row.addWidget(lbl)
        spins = []
        for i, axis in enumerate(("x1", "y1", "x2", "y2")):
            if i:
                row.addSpacing(10)
            axis_lbl = QLabel(axis)
            axis_lbl.setStyleSheet("color: #6b7280;")
            row.addWidget(axis_lbl)
            sp = QSpinBox()
            sp.setRange(0, 9999)
            sp.setFixedWidth(84)
            row.addWidget(sp)
            spins.append(sp)
        row.addStretch()
        return spins, row

    def _make_folder_row(self, label_text: str):
        edit = QLineEdit()
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(self._LABEL_W)
        row.addWidget(lbl)
        row.addWidget(edit)
        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda _, e=edit: self._browse_folder(e))
        row.addWidget(browse)
        return edit, row

    # ------------------------------------------------------------------ load / save

    def _load_values(self):
        config = self.config_manager.load_config()

        self._captures_edit.setText(config.get("captures_folder", ""))
        self._data_edit.setText(config.get("data_folder", "./data"))
        self._clips_edit.setText(config.get("final_clips_folder", "./final_clips"))

        names = config.get("player_names", [])
        self._names_edit.setPlainText("\n".join(names) if isinstance(names, list) else str(names))

        kf = config.get("killfeed_roi", [0, 0, 0, 0])
        for sp, val in zip(self._kf_spins, kf):
            sp.setValue(int(val))

        chat = config.get("chat_roi", [0, 0, 0, 0])
        for sp, val in zip(self._chat_spins, chat):
            sp.setValue(int(val))

        # Whatever resolution the current killfeed_roi/chat_roi were
        # calibrated at; only changes if the user clicks a quick-apply preset
        # below, so hand-tuned values keep whatever they already had.
        self._roi_resolution = config.get("killfeed_roi_resolution")

        idx = self._moments_combo.findData((config.get("moments") or {}).get("mode", "conversations"))
        self._moments_combo.setCurrentIndex(max(0, idx))
        self._subs_check.setChecked(bool((config.get("subtitles") or {}).get("enabled", False)))

    def _save(self):
        # Advanced first: it writes its own keys, which the load below then keeps
        if not self._advanced_tab.save_settings(quiet=True):
            return
        config = self.config_manager.load_config()

        config["captures_folder"] = self._captures_edit.text().strip()
        config["data_folder"] = self._data_edit.text().strip()
        config["final_clips_folder"] = self._clips_edit.text().strip()

        raw_names = self._names_edit.toPlainText()
        config["player_names"] = [n.strip() for n in raw_names.splitlines() if n.strip()]

        config["killfeed_roi"] = [sp.value() for sp in self._kf_spins]
        config["chat_roi"] = [sp.value() for sp in self._chat_spins]
        config["killfeed_roi_resolution"] = self._roi_resolution

        config.setdefault("moments", {})["mode"] = self._moments_combo.currentData()
        config.setdefault("subtitles", {})["enabled"] = self._subs_check.isChecked()

        self.config_manager.save_config(config)
        self.accept()

    # ------------------------------------------------------------------ helpers

    def _browse_folder(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            edit.setText(path)

    def _apply_roi_preset(self, preset: dict):
        for sp, val in zip(self._kf_spins, preset["killfeed_roi"]):
            sp.setValue(val)
        for sp, val in zip(self._chat_spins, preset["chat_roi"]):
            sp.setValue(val)
        self._roi_resolution = preset["resolution"][:]
