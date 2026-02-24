#!/usr/bin/env python3
"""
Face Unlock Guardian (Always-On Face Monitor)
Continuously monitors the camera. If the enrolled user's face is absent for N seconds,
it locks the screen.
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] face-guardian: %(message)s'
)
log = logging.getLogger("face_guardian")

def get_config(key, default):
    try:
        with open("/etc/face-unlock/config.conf") as f:
            for line in f:
                if line.startswith(key):
                    return line.split("=")[1].strip()
    except Exception:
        pass
    return default

def check_face(known_encodings, tolerance) -> dict:
    result = {"authorized": False, "present": False}
    try:
        import face_recognition
        import cv2
    except ImportError as e:
        log.error(f"Missing dependency: {e}")
        # Default to True to prevent accidental lockouts
        return {"authorized": True, "present": True}

    # Open camera briefly
    cap = cv2.VideoCapture(int(os.environ.get("FACE_UNLOCK_CAMERA", "0")))
    if not cap.isOpened():
        # Camera is likely used by another app
        return {"authorized": True, "present": True}

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Read a few frames to let auto-exposure settle
    ret = False
    for _ in range(3):
        ret, frame = cap.read()
    
    cap.release()

    if not ret or frame is None:
        return {"authorized": True, "present": True}
    
    # Check for primary authorized face using HOG
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame, model="hog")
    
    if face_locations:
        result["present"] = True
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=tolerance)
            if any(matches):
                result["authorized"] = True
                return result

    # If not authorized, check if ANY face is still present (profile or looking down)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frontal_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
    
    faces_front = frontal_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces_front) > 0:
        result["present"] = True
        return result
        
    faces_profile = profile_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces_profile) > 0:
        result["present"] = True
        return result
        
    gray_flipped = cv2.flip(gray, 1)
    faces_profile_flip = profile_cascade.detectMultiScale(gray_flipped, 1.3, 5)
    if len(faces_profile_flip) > 0:
        result["present"] = True
        return result
            
    return result

def load_encodings(username: str) -> list:
    import pickle
    try:
        path = Path(f"/etc/face-unlock/encodings/{username}.pkl")
        if not path.exists():
            return []
        with open(path, "rb") as f:
            return pickle.load(f)
    except PermissionError:
        log.warning(f"Permission denied reading encodings for '{username}'. "
                     "Enable Face Guard via the toggle to fix permissions.")
        return []
    except Exception as e:
        log.error(f"Error loading encodings: {e}")
        return []

def is_screen_locked() -> bool:
    try:
        # standard GNOME check
        out = subprocess.check_output(["gdbus", "call", "-e", "-d", "org.gnome.ScreenSaver",
                                       "-o", "/org/gnome/ScreenSaver", "-m", "org.gnome.ScreenSaver.GetActive"],
                                      text=True).strip()
        if "true" in out.lower():
            return True
    except Exception:
        pass
    return False

def lock_screen():
    log.info("Face missing for too long. Locking screen!")
    try:
        # 1. Try locking via loginctl by finding the exact seat/session for the user
        uname = os.environ.get("USER", os.environ.get("LOGNAME", ""))
        if uname:
            # Find all sessions for this user
            sessions_out = subprocess.check_output(["loginctl", "list-sessions", "--no-legend"], text=True)
            for line in sessions_out.strip().splitlines():
                if uname in line:
                    session_id = line.split()[0]
                    log.info(f"Locking loginctl session: {session_id}")
                    subprocess.run(["loginctl", "lock-session", session_id], check=False)
                    
        # 2. Backup: DBus method if loginctl didn't work (e.g., Wayland quirks)
        env = os.environ.copy()
        uid = os.getuid()
        if "XDG_RUNTIME_DIR" not in env:
            env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
            
        subprocess.run(["gdbus", "call", "-e", "-d", "org.gnome.ScreenSaver",
                       "-o", "/org/gnome/ScreenSaver", "-m", "org.gnome.ScreenSaver.Lock"],
                       env=env, check=False)
    except Exception as e:
        log.error(f"Failed to lock screen: {e}")

def main():
    username = os.environ.get("USER", os.environ.get("LOGNAME"))
    if not username:
        log.error("Unknown user")
        sys.exit(1)

    log.info("Face Guardian started.")
    last_seen_time = time.time()
    warning_process = None

    while True:
        try:
            lock_delay = int(get_config("guard_lock_delay", "30"))
            warning_delay = int(get_config("guard_warning_delay", "5"))
        except ValueError:
            lock_delay = 30
            warning_delay = 5
            
        guard_enabled = get_config("guard_enabled", "false").lower() == "true"

        if not guard_enabled or is_screen_locked():
            if warning_process:
                warning_process.terminate()
                warning_process = None
            time.sleep(5)
            last_seen_time = time.time()
            continue

        encodings = load_encodings(username)
        if not encodings:
            log.info(f"No face currently enrolled for '{username}'. Guardian pausing.")
            time.sleep(10)
            continue

        tolerance = float(get_config("threshold", "0.55"))
        face_status = check_face(encodings, tolerance)

        if face_status["authorized"]:
            if warning_process:
                warning_process.terminate()
                warning_process = None
            last_seen_time = time.time()
        else:
            absent_duration = time.time() - last_seen_time
            remaining = int(lock_delay - absent_duration)
            
            # The UI handles the visual countdown. Spawn it only after 
            # warning_delay has passed, if we haven't spawned it yet.
            if warning_process is None and remaining > 0 and absent_duration >= warning_delay:
                script_path = "/usr/local/bin/face-unlock-ui" 
                # fallback or dev mode path if not installed
                if not os.path.exists(script_path):
                    script_path = os.path.join(os.path.dirname(__file__), "..", "ui", "face-unlock-ui")
                
                try:
                    log.info(f"Launching warning UI: {script_path} --mode warning --timeout {remaining}")
                    
                    # Ensure GTK UI has access to the user's graphical session
                    env = os.environ.copy()
                    uid = os.getuid()
                    runtime_dir = f"/run/user/{uid}"
                    env["XDG_RUNTIME_DIR"] = runtime_dir
                    
                    # Auto-detect Wayland socket
                    if os.path.exists(f"{runtime_dir}/wayland-1"):
                        env["WAYLAND_DISPLAY"] = "wayland-1"
                    elif os.path.exists(f"{runtime_dir}/wayland-0"):
                        env["WAYLAND_DISPLAY"] = "wayland-0"
                        
                    
                    # Auto-detect X11 display socket
                    if os.path.exists("/tmp/.X11-unix/X1"):
                        env["DISPLAY"] = ":1"
                    elif os.path.exists("/tmp/.X11-unix/X0"):
                        env["DISPLAY"] = ":0"
                    elif "DISPLAY" not in env:
                        env["DISPLAY"] = ":0" # Final fallback
                        
                    if "XAUTHORITY" not in env:
                        env["XAUTHORITY"] = f"/run/user/{uid}/gdm/Xauthority"
                        
                    if "DBUS_SESSION_BUS_ADDRESS" not in env:
                        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
                        
                    warning_process = subprocess.Popen(
                        [script_path, "--mode", "warning", "--timeout", str(remaining)],
                        env=env,
                        stdout=sys.stdout,
                        stderr=sys.stderr
                    )
                except Exception as e:
                    log.error(f"Failed to launch warning UI: {e}")

            if absent_duration > lock_delay:
                if warning_process:
                    warning_process.terminate()
                    warning_process = None
                lock_screen()
                last_seen_time = time.time() # Reset after locking
                
        time.sleep(2) # Poll roughly every 2 seconds

if __name__ == "__main__":
    main()
