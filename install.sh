#!/usr/bin/env bash
# ============================================================
#  Face Unlock for Ubuntu — Installer
#  Run with: sudo bash install.sh
# ============================================================

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

banner() {
  echo -e "${CYAN}"
  echo "  ╔══════════════════════════════════════════════╗"
  echo "  ║        Face Unlock for Ubuntu  v1.0          ║"
  echo "  ║           Installation Script                ║"
  echo "  ╚══════════════════════════════════════════════╝"
  echo -e "${NC}"
}

info()    { echo -e "${BLUE}  ℹ  ${NC}$*"; }
success() { echo -e "${GREEN}  ✅ ${NC}$*"; }
warn()    { echo -e "${YELLOW}  ⚠  ${NC}$*"; }
error()   { echo -e "${RED}  ❌ ${NC}$*"; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }

# ── Verify root ──────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Please run with sudo: sudo bash install.sh"

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

banner

info "Installing for user: ${BOLD}${REAL_USER}${NC}"
info "Script directory:   ${SCRIPT_DIR}"
echo

# ── Detect Ubuntu version ────────────────────────────────────
step "Detecting system"
. /etc/os-release
info "OS: ${PRETTY_NAME}"
UBUNTU_VER="${VERSION_ID:-22.04}"

if [[ "${UBUNTU_VER}" < "20.04" ]]; then
  error "Ubuntu 20.04+ required. Detected: ${UBUNTU_VER}"
fi
success "Ubuntu ${UBUNTU_VER} supported"

# ── Directories ──────────────────────────────────────────────
LIB_DIR="/usr/local/lib/face-unlock"
CFG_DIR="/etc/face-unlock"
ENC_DIR="${CFG_DIR}/encodings"
BAK_DIR="${CFG_DIR}/backups"
LOG_DIR="/var/log"
PLYMOUTH_THEME_DIR="/usr/share/plymouth/themes/face-unlock"
DESKTOP_DIR="/usr/share/applications"

step "Creating directories"
mkdir -p "${LIB_DIR}" "${CFG_DIR}" "${ENC_DIR}" "${BAK_DIR}" "${PLYMOUTH_THEME_DIR}"
chmod 711 "${ENC_DIR}"
touch "${LOG_DIR}/face-unlock.log"
chmod 622 "${LOG_DIR}/face-unlock.log"
success "Directories created"

# ── System dependencies ──────────────────────────────────────
step "Installing system dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q

PACKAGES=(
  python3-pip python3-dev python3-gi python3-gi-cairo
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-glib-2.0
  libpam-python python3-pam
  cmake build-essential libopencv-dev
  python3-opencv python3-numpy
  libdlib-dev libboost-python-dev
  plymouth plymouth-themes
  policykit-1
  libatlas-base-dev liblapack-dev libblas-dev
  libx11-dev libssl-dev
)

apt-get install -y "${PACKAGES[@]}" 2>&1 | tail -5
success "System packages installed"

# ── Python dependencies ──────────────────────────────────────
step "Installing Python dependencies"

# face_recognition build can take a while (compiles dlib)
info "Installing face_recognition (this may take 5–15 minutes — compiling dlib…)"
echo

PIP_LOG="$(mktemp)"
pip3 install --break-system-packages face_recognition opencv-python \
  >"${PIP_LOG}" 2>&1 &
PIP_PID=$!

# ── Spinner ──────────────────────────────────────────────────
SPINNER_FRAMES=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
SPINNER_IDX=0
START_TS=$(date +%s)

while kill -0 "$PIP_PID" 2>/dev/null; do
  ELAPSED=$(( $(date +%s) - START_TS ))
  MINS=$(( ELAPSED / 60 ))
  SECS=$(( ELAPSED % 60 ))
  FRAME="${SPINNER_FRAMES[$SPINNER_IDX]}"
  printf "\r  ${CYAN}%s${NC}  Compiling & installing…  ${BOLD}%dm %02ds${NC} elapsed   " \
    "$FRAME" "$MINS" "$SECS"
  SPINNER_IDX=$(( (SPINNER_IDX + 1) % ${#SPINNER_FRAMES[@]} ))
  sleep 0.12
done

# Clear spinner line
printf "\r%*s\r" "$(tput cols 2>/dev/null || echo 60)" ""

wait "$PIP_PID"
PIP_EXIT=$?

if [[ $PIP_EXIT -ne 0 ]]; then
  echo
  warn "pip output (last 10 lines):"
  tail -10 "${PIP_LOG}"
  rm -f "${PIP_LOG}"
  error "Python package installation failed (exit $PIP_EXIT)"
fi
rm -f "${PIP_LOG}"

TOTAL=$(( $(date +%s) - START_TS ))
success "Python packages installed  (took ${TOTAL}s)"

# ── Copy library files ───────────────────────────────────────
step "Copying face unlock library files"
cp "${SCRIPT_DIR}/src/face_engine/face_engine.py"  "${LIB_DIR}/"
cp "${SCRIPT_DIR}/src/face_engine/enroll.py"       "${LIB_DIR}/"
cp "${SCRIPT_DIR}/src/pam/pam_face_unlock.py"      "${LIB_DIR}/"
cp "${SCRIPT_DIR}/src/ui/face_unlock_ui.py"        "${LIB_DIR}/"
cp "${SCRIPT_DIR}/src/ui/settings_app.py"          "${LIB_DIR}/"
cp "${SCRIPT_DIR}/src/guardian/face_guardian.py"   "${LIB_DIR}/"
cp "${SCRIPT_DIR}/src/guardian/toggle-guard.sh"    "${LIB_DIR}/"

chmod +x "${LIB_DIR}/"*.py
chmod +x "${LIB_DIR}/toggle-guard.sh"

cp "${SCRIPT_DIR}/src/ui/face-unlock-ui" /usr/local/bin/
chmod +x /usr/local/bin/face-unlock-ui

# ── Lock Face settings app (.desktop entry) ──────────────────
cat > "${DESKTOP_DIR}/face-unlock.desktop" << 'DESKTOP'
[Desktop Entry]
Name=Lock Face
Comment=Manage your face authentication settings
Exec=/usr/bin/python3 /usr/local/lib/face-unlock/settings_app.py
Icon=preferences-system-security
Terminal=false
Type=Application
Categories=Settings;Security;System;
Keywords=Face;Auth;Security;Biometrics;
DESKTOP

success "Library files copied to ${LIB_DIR} and /usr/local/bin"

# ── PAM module ───────────────────────────────────────────────
step "Installing PAM module"
cp "${LIB_DIR}/pam_face_unlock.py" /lib/security/pam_face_unlock.py
chmod 644 /lib/security/pam_face_unlock.py
success "PAM module installed"

# ── PAM configuration ────────────────────────────────────────
step "Configuring PAM (backing up originals)"

# Backup originals
for PAM_FILE in sudo common-auth; do
  if [[ -f "/etc/pam.d/${PAM_FILE}" ]]; then
    cp "/etc/pam.d/${PAM_FILE}" "${BAK_DIR}/${PAM_FILE}.bak"
    info "Backed up /etc/pam.d/${PAM_FILE} → ${BAK_DIR}/${PAM_FILE}.bak"
  fi
done

cp "${SCRIPT_DIR}/src/pam/pam_configs/sudo"        /etc/pam.d/sudo
cp "${SCRIPT_DIR}/src/pam/pam_configs/common-auth" /etc/pam.d/common-auth
chmod 644 /etc/pam.d/sudo /etc/pam.d/common-auth
success "PAM configuration updated"

# ── Plymouth theme ───────────────────────────────────────────
step "Installing Plymouth boot theme"
cp "${SCRIPT_DIR}/src/boot/plymouth-theme/face-unlock.plymouth" "${PLYMOUTH_THEME_DIR}/"
cp "${SCRIPT_DIR}/src/boot/plymouth-theme/face-unlock.script"   "${PLYMOUTH_THEME_DIR}/"

# Install and set as default theme
if command -v update-alternatives &>/dev/null; then
  update-alternatives --install /usr/share/plymouth/themes/default.plymouth \
    default.plymouth "${PLYMOUTH_THEME_DIR}/face-unlock.plymouth" 200 || true
fi

if command -v plymouth-set-default-theme &>/dev/null; then
  plymouth-set-default-theme -R face-unlock 2>/dev/null || \
    warn "Could not set Plymouth theme (may need manual setup)"
fi

success "Plymouth boot theme installed"



# ── Polkit policy ────────────────────────────────────────────
step "Installing Polkit policy"
cat > /usr/share/polkit-1/actions/com.face-unlock.policy << 'POLICY'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="com.face-unlock.enroll">
    <description>Enroll face for Face Unlock</description>
    <message>Authentication is required to enroll your face</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/python3</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>
  </action>

  <action id="com.face-unlock.guard">
    <description>Modify Face Guard settings</description>
    <message>Authentication is required to change Face Guard settings</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/local/lib/face-unlock/toggle-guard.sh</annotate>
  </action>
</policyconfig>
POLICY
success "Polkit policy installed"

# ── GNOME Shell Extension & Guardian Service ─────────────────
step "Installing GNOME Shell Extension and Guardian Service"
EXT_DIR="/usr/share/gnome-shell/extensions/face-unlock@face-unlock.ubuntu"
mkdir -p "${EXT_DIR}"
cp -r "${SCRIPT_DIR}/src/gnome-extension/"* "${EXT_DIR}/"

mkdir -p /etc/systemd/user
cp "${SCRIPT_DIR}/src/guardian/face-guardian.service" /etc/systemd/user/

if command -v gnome-extensions &>/dev/null; then
  # Give proper permissions — files 644, directory needs 755 (execute to enter)
  chmod 755 "${EXT_DIR}"
  find "${EXT_DIR}" -type f -exec chmod 644 {} \;
  # Try to enable if running as user during dev, though it won't work perfectly over sudo
  sudo -u "$REAL_USER" gnome-extensions enable face-unlock@face-unlock.ubuntu 2>/dev/null || true
fi
success "Guardian daemon and GNOME extension installed"

# ── Write default config ─────────────────────────────────────
step "Writing default configuration"
cat > "${CFG_DIR}/config.conf" << 'CONFIG'
# Face Unlock Configuration
# Edit values here or use the Lock Face app

enabled_sudo   = true
enabled_login  = true
threshold      = 0.55
require_attention = false
timeout        = 8
guard_enabled  = false
guard_lock_delay = 30
CONFIG
success "Default config written to ${CFG_DIR}/config.conf"

# Make config user-writable so the Lock Face settings app can save without pkexec
chmod 666 "${CFG_DIR}/config.conf"

# ── Summary ──────────────────────────────────────────────────
echo
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅  Face Unlock installed successfully!     ${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
echo
info "Next steps:"
echo
echo -e "  ${BOLD}1. Enroll your face:${NC}"
echo -e "     ${CYAN}sudo bash enroll.sh${NC}"
echo
echo -e "  ${BOLD}2. Test sudo face unlock:${NC}"
echo -e "     ${CYAN}sudo ls /root${NC}   ← should show face unlock UI"
echo
echo -e "  ${BOLD}3. Open Settings:${NC}"
echo -e "     Search '${CYAN}Lock Face${NC}' in the app menu"
echo
echo -e "  ${BOLD}4. Preview the UI animations:${NC}"
echo -e "     ${CYAN}python3 ${LIB_DIR}/face_unlock_ui.py --demo${NC}"
echo
warn "If sudo stops working: restore PAM with 'sudo bash uninstall.sh'"
echo
