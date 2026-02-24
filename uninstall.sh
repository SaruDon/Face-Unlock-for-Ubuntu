#!/usr/bin/env bash
# ============================================================
#  Face Unlock — Uninstaller
#  Safely removes all components and restores original PAM
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

[[ $EUID -eq 0 ]] || { echo -e "${RED}Run with sudo${NC}"; exit 1; }

echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════╗"
echo "  ║   Face Unlock — Uninstaller     ║"
echo "  ╚══════════════════════════════════╝"
echo -e "${NC}"

BAK_DIR="/etc/face-unlock/backups"

# Restore PAM configs
echo -e "${BOLD}▶ Restoring original PAM configuration${NC}"
for PAM_FILE in sudo common-auth; do
  BAK="${BAK_DIR}/${PAM_FILE}.bak"
  if [[ -f "${BAK}" ]]; then
    cp "${BAK}" "/etc/pam.d/${PAM_FILE}"
    echo -e "  ${GREEN}✅${NC} Restored /etc/pam.d/${PAM_FILE}"
  else
    echo -e "  ${YELLOW}⚠${NC}  No backup for ${PAM_FILE} — skipping"
  fi
done

# Stop Face Guardian for active users
echo -e "\n${BOLD}▶ Stopping Face Guardian service${NC}"
for uid in $(ls /run/user/ 2>/dev/null); do
  sudo -u "#$uid" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user stop face-guardian.service 2>/dev/null || true
  sudo -u "#$uid" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user disable face-guardian.service 2>/dev/null || true
done
echo -e "  ${GREEN}✅${NC} Guardian stopped"

# Remove installed files
echo -e "\n${BOLD}▶ Removing installed files${NC}"
rm -rf /usr/local/lib/face-unlock
rm -rf /etc/face-unlock
rm -f  /lib/security/pam_face_unlock.py
rm -f  /usr/local/bin/face-unlock-ui
rm -f  /usr/share/applications/face-unlock.desktop
rm -rf /usr/share/plymouth/themes/face-unlock
rm -rf /usr/share/gnome-shell/extensions/face-unlock@face-unlock.ubuntu
rm -f  /usr/share/polkit-1/actions/com.face-unlock.policy
rm -f  /etc/systemd/user/face-guardian.service
rm -f  /var/log/face-unlock.log
echo -e "  ${GREEN}✅${NC} Files removed"

# Restore Plymouth theme
echo -e "\n${BOLD}▶ Restoring default Plymouth theme${NC}"
if command -v plymouth-set-default-theme &>/dev/null; then
  plymouth-set-default-theme -R default 2>/dev/null || true
fi
echo -e "  ${GREEN}✅${NC} Plymouth restored"

echo
echo -e "${GREEN}${BOLD}✅ Face Unlock fully removed. System restored.${NC}"
echo
