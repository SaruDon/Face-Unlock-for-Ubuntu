#!/bin/bash
# Face Guard Toggle (Polkit protected)
# Usage: toggle-guard.sh <enable|disable>

CONFIG_FILE="/etc/face-unlock/config.conf"
STATE=$1

if [[ -z "$STATE" ]]; then
    echo "Usage: $0 <enable|disable>"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run with sudo"
   exit 1
fi

# Ensure config file exists
mkdir -p "$(dirname "$CONFIG_FILE")"
touch "$CONFIG_FILE"

# Make sure guard_enabled key exists
if ! grep -q "^guard_enabled" "$CONFIG_FILE"; then
    echo "guard_enabled = false" >> "$CONFIG_FILE"
fi

if [[ "$STATE" == "enable" ]]; then
    sed -i 's/^guard_enabled.*/guard_enabled = true/' "$CONFIG_FILE"
    
    # Ensure encoding files are readable by the user (service runs as user)
    # Give read access to the encodings directory and files
    chmod -R 755 /etc/face-unlock/encodings/ 2>/dev/null || true
    
    # Start service for active users
    for uid in $(ls /run/user/ 2>/dev/null); do
        sudo -u "#$uid" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user start face-guardian.service || true
    done

elif [[ "$STATE" == "disable" ]]; then
    sed -i 's/^guard_enabled.*/guard_enabled = false/' "$CONFIG_FILE"
    
    # Stop service for active users
    for uid in $(ls /run/user/ 2>/dev/null); do
        sudo -u "#$uid" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user stop face-guardian.service || true
    done
fi
