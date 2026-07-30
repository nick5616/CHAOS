# CHAOS Desktop Application - Design Document

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Core Features](#core-features)
5. [UI Components](#ui-components)
6. [Implementation Phases](#implementation-phases)
7. [Technical Specifications](#technical-specifications)
8. [File Structure](#file-structure)
9. [API Interfaces](#api-interfaces)

---

## Overview

### Purpose

Transform the CHAOS command-line tool into a user-friendly desktop application that automates CS2 highlight detection and clipping with an intuitive GUI.

### Key Benefits

-   **Visual ROI Configuration**: Drag-and-drop regions of interest on actual gameplay footage
-   **Automated Setup**: CUDA detection and PyTorch installation
-   **Real-time Progress**: Live pipeline execution with progress tracking
-   **User-Friendly**: No command-line knowledge required

### Target Users

-   CS2 content creators
-   Streamers
-   Gaming enthusiasts
-   Non-technical users

---

## Architecture

### Technology Stack

```
Frontend: PyQt6 (Cross-platform GUI)
Backend: Existing chaos_lib modules (unchanged)
Pipeline: Existing main.py as driver (unchanged)
Configuration: YAML with GUI management
Video Processing: OpenCV + FFmpeg
AI Models: EasyOCR + Whisper
```

### System Requirements

-   **Python**: 3.8+
-   **OS**: Windows 10+, macOS 10.15+, Ubuntu 18.04+
-   **RAM**: 8GB minimum, 16GB recommended
-   **GPU**: NVIDIA GPU with CUDA support (optional)
-   **Storage**: 2GB free space

---

## Project Structure

```
CHAOS/
├── chaos_lib/                    # Existing core library (unchanged)
│   ├── __init__.py
│   ├── analyzers.py
│   ├── clipper.py
│   ├── correlator.py
│   ├── ingestion.py
│   └── summary.py
│
├── pipeline/                     # Existing pipeline driver (unchanged)
│   └── main.py                   # Command-line interface
│
├── desktop_app/                  # New desktop application
│   ├── __init__.py
│   ├── main_gui.py              # GUI entry point
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py       # Main window class
│   │   ├── tabs/
│   │   │   ├── __init__.py
│   │   │   ├── setup_tab.py     # System setup
│   │   │   ├── config_tab.py    # Configuration
│   │   │   ├── pipeline_tab.py  # Pipeline execution
│   │   │   ├── results_tab.py   # Results management
│   │   │   └── advanced_tab.py  # Advanced settings
│   │   ├── widgets/
│   │   │   ├── __init__.py
│   │   │   ├── video_player.py  # Video player widget
│   │   │   ├── roi_configurator.py # ROI configuration
│   │   │   ├── progress_bar.py  # Progress tracking
│   │   │   ├── log_viewer.py    # Log display
│   │   │   └── clip_preview.py  # Clip preview
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── config_manager.py # Configuration management
│   │       ├── system_detector.py # System detection
│   │       ├── error_handler.py  # Error handling
│   │       └── theme_manager.py  # UI theming
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── pipeline_worker.py   # Background pipeline execution
│   │   ├── setup_worker.py      # System setup worker
│   │   └── detection_worker.py  # ROI detection testing
│   └── resources/
│       ├── icons/               # Application icons
│       ├── themes/              # UI themes
│       └── templates/           # UI templates
│
├── data/                        # Existing data directory (unchanged)
├── final_clips/                 # Existing clips directory (unchanged)
├── venv/                        # Existing virtual environment (unchanged)
├── config.yaml                  # Existing configuration (unchanged)
├── requirements.txt             # Existing requirements (unchanged)
├── setup.sh                     # Existing setup script (unchanged)
├── setup.bat                    # Existing setup script (unchanged)
├── tuner.py                     # Existing tuning tool (unchanged)
├── README.md                    # Existing documentation (unchanged)
└── DESKTOP_APP_DESIGN.md        # This design document
```

---

## Core Features

### 1. Setup Tab

**Purpose**: First-time system configuration and dependency installation

**Components**:

-   System requirements checker
-   FFmpeg installation/verification
-   CUDA detection and PyTorch installation
-   Dependencies installation with progress tracking

**User Flow**:

1. Launch app → Setup tab opens automatically
2. System check runs automatically
3. Missing dependencies installed with progress bar
4. Success confirmation → Navigate to Configure tab

### 2. Configure Tab

**Purpose**: Application configuration with visual ROI setup

**Components**:

-   File path configuration (browse buttons)
-   Player names management (simple text area)
-   Video-based ROI configuration
-   Configuration validation and testing

**User Flow**:

1. Set file paths using browse buttons
2. Enter player names (one per line)
3. Load video and configure ROI regions
4. Test detection and save configuration

### 3. Pipeline Tab

**Purpose**: Execute the CHAOS processing pipeline

**Components**:

-   Stage selection buttons (Ingest, Analyze, Correlate, Clip, Summary)
-   Real-time progress tracking
-   Live log output
-   Pipeline control (start, pause, stop, reset)

**User Flow**:

1. Review configuration
2. Select stages to run
3. Start pipeline execution
4. Monitor progress and logs
5. View results when complete

### 4. Results Tab

**Purpose**: Manage and preview generated clips

**Components**:

-   Clip thumbnail grid
-   Individual clip preview player
-   Metadata display (score, tags, events)
-   Export options (individual, batch)

**User Flow**:

1. View generated clips
2. Preview clips in player
3. Review scores and tags
4. Export desired clips

### 5. Advanced Settings Tab

**Purpose**: Fine-tune detection parameters (hidden by default)

**Components**:

-   HSV color range sliders
-   Shape detection parameters
-   Timing configuration
-   Scoring weights adjustment

---

## UI Components

### Main Window Layout

```
┌─────────────────────────────────────────────────────────────┐
│ CHAOS - CS2 Highlight Analysis & Organization System        │
├─────────────────────────────────────────────────────────────┤
│ [Setup] [Configure] [Pipeline] [Results] [Advanced]         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Current Tab Content Area                                   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Status: Ready | Progress: ████████░░ 80% | Last: 2 clips   │
└─────────────────────────────────────────────────────────────┘
```

### Video ROI Configuration

```
┌─────────────────────────────────────────────────────────────┐
│ Region of Interest Configuration                           │
├─────────────────────────────────────────────────────────────┤
│ Video Source: [Auto-detect] [Browse...] demo_001.mp4 │
│                                                             │
│ [] [] [] [] [00:45.2 / 12:30.8] [] [1x]      │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Video Frame (1920x1080) with ROI Overlays              │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │     ┌─── Killfeed ROI ───┐                         │ │ │
│ │ │     │  Kill detected  │                         │ │ │
│ │ │     │  T-side player  │                         │ │ │
│ │ │     └───────────────────┘                         │ │ │
│ │ │                                                     │ │ │
│ │ │  ┌─── Chat ROI ───┐                                │ │ │
│ │ │  │ Enemy rage  │                                │ │ │
│ │ │  │ Team hype   │                                │ │ │
│ │ │  └───────────────┘                                │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Killfeed ROI: [1920, 40, 2550, 300] - Contains kills   │
│ Chat ROI: [30, 1150, 650, 1300] - Contains chat        │
│                                                             │
│ [Reset ROI] [Test Detection] [Save Configuration]          │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal**: Basic GUI framework and setup functionality

**Deliverables**:

-   Main window with tab navigation
-   Setup tab with system detection
-   Basic configuration loading/saving
-   FFmpeg installation automation

**Files to Create**:

-   `desktop_app/main_gui.py` - Main application window
-   `desktop_app/gui/tabs/setup_tab.py` - System setup functionality
-   `desktop_app/gui/utils/config_manager.py` - Configuration management
-   `desktop_app/gui/utils/system_detector.py` - System requirements detection

### Phase 2: Configuration (Week 3-4)

**Goal**: Visual ROI configuration with video player

**Deliverables**:

-   Video player with seeking controls
-   Drag-and-drop ROI configuration
-   Configuration validation
-   Player names management

**Files to Create**:

-   `desktop_app/gui/tabs/config_tab.py` - Main configuration interface
-   `desktop_app/gui/widgets/video_player.py` - Video-based ROI setup
-   `desktop_app/gui/widgets/roi_configurator.py` - Interactive video display
-   `desktop_app/gui/utils/screenshot_detector.py` - Auto video detection

### Phase 3: Pipeline Execution (Week 5-6)

**Goal**: Pipeline execution with progress tracking

**Deliverables**:

-   Pipeline execution interface
-   Real-time progress tracking
-   Live log output
-   Pipeline control (start/stop/pause)

**Files to Create**:

-   `desktop_app/gui/tabs/pipeline_tab.py` - Pipeline execution interface
-   `desktop_app/workers/pipeline_worker.py` - Background pipeline execution
-   `desktop_app/gui/widgets/progress_bar.py` - Progress monitoring
-   `desktop_app/gui/widgets/log_viewer.py` - Real-time log display

### Phase 4: Results & Polish (Week 7-8)

**Goal**: Results management and application polish

**Deliverables**:

-   Results tab with clip management
-   Advanced settings tab
-   Error handling and validation
-   Application packaging

**Files to Create**:

-   `desktop_app/gui/tabs/results_tab.py` - Results management interface
-   `desktop_app/gui/tabs/advanced_tab.py` - Advanced configuration
-   `desktop_app/gui/widgets/clip_preview.py` - Clip preview player
-   `desktop_app/gui/utils/error_handler.py` - Error management

---

## Technical Specifications

### Dependencies

```txt
# GUI Framework (add to requirements.txt)
PyQt6>=6.5.0
PyQt6-tools>=6.5.0

# Enhanced functionality
opencv-python>=4.8.0
Pillow>=10.0.0
psutil>=5.9.0

# Existing CHAOS dependencies (unchanged)
pyyaml
pandas
tqdm
easyocr
openai-whisper
librosa
thefuzz
```

### Configuration Schema

```yaml
# GUI-specific settings (add to config.yaml)
gui:
    window_size: [1200, 800]
    theme: "default"
    auto_save: true

# System settings
system:
    cuda_available: false
    pytorch_version: "cpu"
    ffmpeg_path: "ffmpeg"

# ROI configuration
roi:
    killfeed: [1920, 40, 2550, 300]
    chat: [30, 1150, 650, 1300]
    video_source: "auto"

# Pipeline settings
pipeline:
    auto_start: false
    show_logs: true
    save_debug: false
```

### Error Handling Strategy

-   **Graceful Degradation**: App continues working even if some features fail
-   **User-Friendly Messages**: Clear error messages with suggested solutions
-   **Logging**: Comprehensive logging for debugging
-   **Recovery**: Automatic retry mechanisms for transient failures

---

## API Interfaces

### Configuration Manager

```python
class ConfigManager:
    def load_config(self) -> dict
    def save_config(self, config: dict) -> bool
    def validate_config(self, config: dict) -> list[str]
    def reset_to_defaults(self) -> dict
    def export_config(self, path: str) -> bool
    def import_config(self, path: str) -> bool
```

### System Detector

```python
class SystemDetector:
    def check_python_version(self) -> tuple[bool, str]
    def check_ffmpeg(self) -> tuple[bool, str]
    def detect_cuda(self) -> dict
    def get_pytorch_command(self) -> str
    def check_dependencies(self) -> dict
```

### Pipeline Worker

```python
class PipelineWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    stage_completed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def run_pipeline(self, stages: list[str])
    def pause_pipeline(self)
    def stop_pipeline(self)
    def get_logs(self) -> list[str]
```

### Video ROI Configurator

```python
class VideoROIConfigurator(QWidget):
    roi_changed = pyqtSignal(dict)

    def load_video(self, path: str) -> bool
    def set_roi(self, roi_type: str, coordinates: list)
    def test_detection(self) -> dict
    def export_roi(self) -> dict
```

---

## Success Metrics

### User Experience

-   **Setup Time**: < 5 minutes from download to first run
-   **Configuration Time**: < 10 minutes for complete setup
-   **Pipeline Execution**: Clear progress indication and error handling
-   **Results Management**: Easy clip preview and export

### Technical Performance

-   **Memory Usage**: < 2GB during normal operation
-   **CPU Usage**: < 50% during pipeline execution
-   **Startup Time**: < 10 seconds on modern hardware
-   **Error Rate**: < 1% for common operations

### Compatibility

-   **Cross-Platform**: Windows 10+, macOS 10.15+, Ubuntu 18.04+
-   **GPU Support**: Automatic CUDA detection and PyTorch installation
-   **Resolution Support**: 1080p, 1440p, 4K video processing
-   **Format Support**: MP4, AVI, MOV, MKV input formats

---

## Development Notes

### Code Organization

-   **Separation of Concerns**: GUI logic separate from business logic
-   **Modular Design**: Each tab and widget is independently testable
-   **Error Boundaries**: Graceful error handling at each level
-   **Resource Management**: Proper cleanup of video resources and threads

### Integration with Existing Code

-   **chaos_lib**: Import and use existing modules unchanged
-   **pipeline/main.py**: Use as backend driver for pipeline execution
-   **config.yaml**: Extend existing configuration schema
-   **requirements.txt**: Add GUI dependencies to existing file

### Testing Strategy

-   **Unit Tests**: Individual component testing
-   **Integration Tests**: Tab and widget interaction testing
-   **UI Tests**: Automated GUI testing with PyQt6 test framework
-   **Performance Tests**: Memory and CPU usage monitoring

### Deployment

-   **Packaging**: PyInstaller for standalone executables
-   **Installation**: Simple installer for each platform
-   **Updates**: Built-in update mechanism
-   **Documentation**: In-app help and external documentation

---

## Getting Started

### Development Setup

1. **Clone Repository**: `git clone <repo-url>`
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Run Desktop App**: `python desktop_app/main_gui.py`
4. **Run Command Line**: `python pipeline/main.py analyze --debug`

### Entry Points

-   **Desktop App**: `python desktop_app/main_gui.py`
-   **Command Line**: `python pipeline/main.py <stage>`
-   **Tuning Tool**: `python tuner.py <video_path> <start_time>`

---

_This design document provides a comprehensive blueprint for implementing the CHAOS desktop application. Each phase can be implemented independently while maintaining the overall architecture and user experience goals. The existing codebase remains unchanged, with the desktop app as a new layer on top._
