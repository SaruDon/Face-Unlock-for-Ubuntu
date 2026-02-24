#!/usr/bin/env bash
# ============================================================
#  Face Unlock — Face Enrollment Wizard
#  Run with: sudo bash enroll.sh
# ============================================================
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run with: sudo bash enroll.sh"; exit 1; }

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
LIB_DIR="/usr/local/lib/face-unlock"

if [[ ! -f "${LIB_DIR}/enroll.py" ]]; then
  echo "❌ Face Unlock not installed. Run 'sudo bash install.sh' first."
  exit 1
fi

echo ""
echo "  ╔═══════════════════════════════════╗"
echo "  ║   Face Unlock — Enrollment        ║"
echo "  ╚═══════════════════════════════════╝"
echo ""
echo "  Enrolling face for user: ${REAL_USER}"
echo ""

python3 "${LIB_DIR}/enroll.py" --user "${REAL_USER}" "$@"
