# CHAOS Desktop Application

A user-friendly GUI for the CHAOS CS2 Highlight Analysis & Organization System.

## Quick Start

### Run the Desktop App

```bash
# From the project root
python run_desktop_app.py

# Or directly
python desktop_app/main_gui.py
```

### Run the Command Line Tool

```bash
# From the project root
python main.py analyze --debug
```

## Features

### Phase 1: Foundation (Completed)

-   **Main Window**: PyQt6-based GUI with tab navigation
-   **Setup Tab**: System requirements detection and dependency installation
-   **Configuration Manager**: YAML-based configuration loading/saving
-   **System Detector**: Automatic detection of Python, FFmpeg, CUDA, and dependencies
-   **Cross-platform**: Works on Windows, macOS, and Linux

### Phase 2: Configuration (In Progress)

-   Video-based ROI configuration with drag-and-drop
-   Player names management
-   Configuration validation and testing

### Phase 3: Pipeline (Planned)

-   Pipeline execution with progress tracking
-   Real-time log output
-   Pipeline control (start/stop/pause)

### Phase 4: Results (Planned)

-   Clip management and preview
-   Export options
-   Statistics dashboard

## Architecture

```
desktop_app/
├── main_gui.py              # Main entry point
├── gui/
│   ├── main_window.py       # Main window class
│   ├── tabs/                # Tab components
│   ├── widgets/             # Custom widgets
│   └── utils/               # Utility classes
├── workers/                 # Background workers
└── resources/               # Icons, themes, templates
```

## Dependencies

-   **PyQt6**: GUI framework
-   **Pillow**: Image processing
-   **psutil**: System monitoring
-   **Existing CHAOS dependencies**: All chaos_lib modules

## Development

The desktop app is designed to work alongside the existing command-line tool:

-   **chaos_lib/**: Core functionality (unchanged)
-   **pipeline/main.py**: Command-line interface (unchanged)
-   **desktop_app/**: New GUI layer
-   **config.yaml**: Shared configuration

## Next Steps

1. **Phase 2**: Implement video ROI configuration
2. **Phase 3**: Add pipeline execution interface
3. **Phase 4**: Create results management system
4. **Polish**: Error handling, theming, and packaging
