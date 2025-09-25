#!/bin/bash
# Simple fix for macOS installation

echo "Fixing CHAOS macOS installation (no sudo required)..."

# Copy the app bundle to system Applications folder (user can do this manually)
echo "To fix the installation:"
echo "1. Open Finder"
echo "2. Go to ~/Applications/ (press Cmd+Shift+G, type ~/Applications)"
echo "3. Drag CHAOS.app to /Applications/ folder"
echo "4. Enter your password when prompted"
echo ""
echo "Alternative: Run this command in Terminal:"
echo "sudo mv ~/Applications/CHAOS.app /Applications/"
echo ""

# For now, let's just register the current app with Launch Services
echo "Registering current app with Launch Services..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f ~/Applications/CHAOS.app

echo ""
echo "Current status:"
echo "📱 CHAOS.app is in ~/Applications/CHAOS.app"
echo "📁 CHAOS files are in ~/Applications/CHAOS/"
echo ""
echo "To make it searchable in Spotlight:"
echo "1. Move CHAOS.app to /Applications/ folder"
echo "2. Wait 2-3 minutes for Spotlight to index"
echo "3. Search for 'CHAOS' in Spotlight"
