# CHAOS Desktop Application - Installation Guide

## 🚀 Quick Installation

### macOS/Linux
```bash
# Download and run the installer
./install_chaos.sh
```

### Windows
```cmd
# Download and run the installer
install_chaos.bat
```

## 📋 What the Installer Does

1. **Creates Installation Directory**: `~/Applications/CHAOS/` (macOS/Linux) or `%USERPROFILE%\Applications\CHAOS\` (Windows)
2. **Copies Application Files**: All necessary files from the source directory
3. **Creates Virtual Environment**: Isolated Python environment with exact dependencies
4. **Installs Dependencies**: Automatically installs all required Python packages
5. **Creates Launcher**: Simple script to start the application
6. **Optional Desktop Shortcut**: Creates a desktop shortcut for easy access
7. **macOS App Bundle**: Creates a proper `.app` bundle for macOS

## 🧪 Testing the Installation

### Test the Setup Process
The installer creates a completely separate installation, so you can test the setup tab by:

1. **Install the app**: `./install_chaos.sh`
2. **Run the installed app**: `~/Applications/CHAOS/start_chaos.sh`
3. **Go to Setup tab**: It should detect that dependencies are already installed
4. **Test uninstall**: `~/Applications/CHAOS/uninstall.sh`

### Verify Installation
```bash
# Run the test script
./test_installation.sh
```

## 📁 Installation Structure

```
~/Applications/CHAOS/
├── chaos_lib/              # Core CHAOS functionality
├── desktop_app/            # GUI application
├── venv/                   # Virtual environment
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── start_chaos.sh          # Launcher script
├── uninstall.sh            # Uninstaller
└── setup.sh               # Setup script
```

## 🔧 Virtual Environment Benefits

- **No Performance Impact**: Virtual environments are just directory structures
- **Isolation**: Won't conflict with other Python applications
- **Reproducible**: Exact dependency versions guaranteed
- **Clean Uninstall**: Complete removal without affecting system
- **Cross-platform**: Works identically on all operating systems

## 🗑️ Uninstalling

### Automatic Uninstall
```bash
# Run the uninstaller
~/Applications/CHAOS/uninstall.sh
```

### Manual Uninstall
```bash
# Remove installation directory
rm -rf ~/Applications/CHAOS

# Remove desktop shortcut (if created)
rm ~/Desktop/CHAOS.desktop

# Remove macOS app bundle (if created)
rm -rf ~/Applications/CHAOS.app
```

## 🐛 Troubleshooting

### Installation Fails
- Ensure Python 3.8+ is installed
- Check internet connection for dependency downloads
- Verify you have write permissions to `~/Applications/`

### App Won't Start
- Run the test script: `./test_installation.sh`
- Check virtual environment: `~/Applications/CHAOS/venv/bin/python --version`
- Try manual activation: `cd ~/Applications/CHAOS && source venv/bin/activate && python desktop_app/main_gui.py`

### Dependencies Missing
- Reinstall: `~/Applications/CHAOS/uninstall.sh` then `./install_chaos.sh`
- Manual fix: `cd ~/Applications/CHAOS && source venv/bin/activate && pip install -r requirements.txt`

## 📦 Distribution

### For End Users
1. **Portable Package**: Zip the entire project directory
2. **Include Installers**: `install_chaos.sh` and `install_chaos.bat`
3. **Include README**: This installation guide

### For Developers
1. **Git Clone**: `git clone <repo>`
2. **Setup**: `./setup.sh` (development setup)
3. **Run**: `python run_desktop_app.py`

## 🔄 Updates

To update CHAOS:
1. **Uninstall**: `~/Applications/CHAOS/uninstall.sh`
2. **Download new version**
3. **Reinstall**: `./install_chaos.sh`

The installer will preserve your configuration file if you choose to reinstall.
