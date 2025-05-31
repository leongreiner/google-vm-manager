#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="/usr/share/applications/google-vm-manager.desktop"
ICON_DIR="/usr/share/icons/hicolor/64x64/apps"
ICON_FILE="$ICON_DIR/google-vm-manager.png"
SOURCE_ICON="$SCRIPT_DIR/google-vm-manager.png"

echo "Creating system-wide desktop entry for Google VM Manager..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script needs to be run with sudo for system-wide installation."
    echo "Usage: sudo ./create_desktop_entry.sh"
    exit 1
fi

# Create icon directory if it doesn't exist
mkdir -p "$ICON_DIR"

# Copy the existing icon to system directory
if [ -f "$SOURCE_ICON" ]; then
    cp "$SOURCE_ICON" "$ICON_FILE"
    chmod 644 "$ICON_FILE"
    echo "✅ Application icon installed: $ICON_FILE"
else
    echo "❌ Icon file not found: $SOURCE_ICON"
    echo "Using system icon instead."
    ICON_NAME="network-server"
fi

# Create the system-wide desktop entry
if [ -f "$SOURCE_ICON" ]; then
    ICON_NAME="google-vm-manager"
else
    ICON_NAME="network-server"
fi

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Google VM Manager
Comment=Control Google Cloud VM instances with VNC support
Exec=python3 "$SCRIPT_DIR/google_vm_gui.py"
Icon=$ICON_NAME
Terminal=false
Categories=Network;System;
StartupNotify=true
EOF

# Make the desktop file readable by all users
chmod 644 "$DESKTOP_FILE"

echo "✅ System-wide desktop entry created: $DESKTOP_FILE"
echo ""
echo "The Google VM Manager should now appear in all users' applications menu."
echo "You can also run it from the command line with: python3 $SCRIPT_DIR/google_vm_gui.py"

# Update desktop database and icon cache
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null
    echo "✅ Desktop database updated"
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null
    echo "✅ Icon cache updated"
fi

echo ""
echo "🚀 System-wide setup complete! Look for 'Google VM Manager' in your applications menu."
echo "💡 Note: All users on this system can now access the application."
