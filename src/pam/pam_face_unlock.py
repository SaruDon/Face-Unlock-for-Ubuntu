#!/usr/bin/env python3
"""
Face Unlock — PAM Module
Pluggable Authentication Module using libpam-python

Installed to: /lib/security/pam_face_unlock.py
Invoked by PAM via pam_python.so

PAM returns:
  PAM_SUCCESS (0)  — face matched, grant access
  PAM_AUTH_ERR (7) — no match, triggers next PAM module (password fallback)
"""

import os
import sys
import subprocess
import logging

# PAM return codes
PAM_SUCCESS     = 0
PAM_AUTH_ERR    = 7
PAM_IGNORE      = 25

FACE_ENGINE_PATH = "/usr/local/lib/face-unlock/face_engine.py"
FACE_UI_PATH     = "/usr/local/bin/face-unlock-ui"

log = logging.getLogger("pam_face_unlock")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s pam_face_unlock[%(process)d]: %(message)s',
    handlers=[logging.FileHandler("/var/log/face-unlock.log")]
)

def get_timeout() -> int:
    try:
        with open("/etc/face-unlock/config.conf") as f:
            for line in f:
                if line.startswith("timeout"):
                    return int(line.split("=")[1].strip())
    except Exception:
        pass
    return 8

def pam_sm_authenticate(pamh, flags, argv):
    """Called by PAM to authenticate a user."""
    try:
        # Get the user being authenticated
        try:
            username = pamh.get_user(None)
        except pamh.exception:
            log.warning("Could not determine PAM user")
            return PAM_AUTH_ERR

        log.info(f"Face unlock attempt for user: {username}")

        # Check if face data is enrolled
        encoding_path = f"/etc/face-unlock/encodings/{username}.pkl"
        if not os.path.exists(encoding_path):
            log.info(f"No face enrolled for '{username}', skipping face auth")
            return PAM_IGNORE

        # Launch UI process + face engine together
        # UI runs in background for visual feedback
        ui_proc = None
        timeout_val = get_timeout()
        try:
            # Launch the UI wrapper script (handles getting user's display env)
            env = os.environ.copy()
            env["SUDO_USER"] = username
            ui_proc = subprocess.Popen(
                [FACE_UI_PATH, "--mode", "scanning", "--timeout", str(timeout_val)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            log.warning(f"Could not launch UI: {e}")

        # Run face recognition
        result = run_face_engine(username)

        if result == "match":
            log.info(f"Face authentication SUCCEEDED for '{username}'")
            # Signal UI: success
            if ui_proc:
                ui_proc.terminate()
                launch_ui_state("success", username)
            return PAM_SUCCESS
        else:
            log.info(f"Face authentication FAILED for '{username}' (result={result})")
            # Signal UI: failed → show password fallback
            if ui_proc:
                ui_proc.terminate()
                launch_ui_state("failed", username)
            return PAM_AUTH_ERR

    except Exception as e:
        log.error(f"Unexpected error in PAM module: {e}")
        return PAM_AUTH_ERR

def run_face_engine(username: str) -> str:
    """
    Runs the face engine as a subprocess.
    Returns: 'match', 'no_match', 'timeout', 'camera_error', etc.
    """
    try:
        proc = subprocess.run(
            [sys.executable, FACE_ENGINE_PATH, "--user", username],
            capture_output=True,
            timeout=15,
            text=True
        )
        # Parse result from stdout
        for line in proc.stderr.splitlines():
            if line.startswith("Result:"):
                return line.split(":", 1)[1].strip()
        return "no_match" if proc.returncode != 0 else "match"
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception as e:
        log.error(f"Face engine error: {e}")
        return "camera_error"

def launch_ui_state(state: str, username: str = ""):
    """Launch UI briefly to show success/failure state."""
    try:
        env = os.environ.copy()
        if username:
            env["SUDO_USER"] = username
        subprocess.Popen(
            [FACE_UI_PATH, "--mode", state],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def pam_sm_setcred(pamh, flags, argv):
    return PAM_SUCCESS

def pam_sm_acct_mgmt(pamh, flags, argv):
    return PAM_SUCCESS

def pam_sm_open_session(pamh, flags, argv):
    return PAM_SUCCESS

def pam_sm_close_session(pamh, flags, argv):
    return PAM_SUCCESS

def pam_sm_chauthtok(pamh, flags, argv):
    return PAM_SUCCESS

# ─── CLI test mode ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Test mode: run face auth without PAM")
    parser.add_argument("--user", default=os.environ.get("USER"))
    args = parser.parse_args()

    if args.test:
        result = run_face_engine(args.user)
        print(f"Face engine result: {result}")
        sys.exit(0 if result == "match" else 1)
