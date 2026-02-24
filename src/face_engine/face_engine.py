#!/usr/bin/env python3
"""
Face Unlock Engine for Ubuntu
Core face recognition module using OpenCV + face_recognition (dlib)
"""

import os
import sys
import time
import pickle
import logging
import numpy as np
from enum import Enum
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger("face_engine")

# ─── Constants ───────────────────────────────────────────────────────────────

ENCODINGS_DIR   = Path("/etc/face-unlock/encodings")
CAMERA_INDEX    = int(os.environ.get("FACE_UNLOCK_CAMERA", "0"))
CONFIDENCE_THRESHOLD = float(os.environ.get("FACE_UNLOCK_THRESHOLD", "0.55"))
MAX_ATTEMPTS    = int(os.environ.get("FACE_UNLOCK_ATTEMPTS", "20"))   # frames to try
TIMEOUT_SECONDS = float(os.environ.get("FACE_UNLOCK_TIMEOUT", "8.0"))
FRAME_WIDTH     = 640
FRAME_HEIGHT    = 480

class AuthResult(Enum):
    MATCH        = "match"
    NO_MATCH     = "no_match"
    NO_FACE      = "no_face"
    CAMERA_ERROR = "camera_error"
    NO_ENCODINGS = "no_encodings"
    TIMEOUT      = "timeout"

# ─── Encoding Storage ─────────────────────────────────────────────────────────

def get_encoding_path(username: str) -> Path:
    return ENCODINGS_DIR / f"{username}.pkl"

def save_encodings(username: str, encodings: list) -> bool:
    ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = get_encoding_path(username)
    with open(path, "wb") as f:
        pickle.dump(encodings, f)
    
    # Secure the file: make it owned by the user so the guardian service can read it,
    # but keep it chmod 600 so other users cannot read it.
    try:
        import shutil
        shutil.chown(path, user=username)
    except Exception as e:
        log.warning(f"Could not chown {path} to {username}: {e}")
    
    os.chmod(path, 0o600)
    log.info(f"Saved {len(encodings)} encodings for user '{username}'")
    return True

def load_encodings(username: str) -> list:
    path = get_encoding_path(username)
    if not path.exists():
        log.warning(f"No encodings found for user '{username}'")
        return []
    with open(path, "rb") as f:
        encodings = pickle.load(f)
    log.info(f"Loaded {len(encodings)} encodings for user '{username}'")
    return encodings

# ─── Face Recognition ─────────────────────────────────────────────────────────

def authenticate(username: str, progress_callback=None) -> AuthResult:
    """
    Main authentication function.
    Opens camera, tries to match face against enrolled encodings.
    Returns AuthResult enum value.

    progress_callback(state: str, data: dict) — optional live updates
    """
    try:
        import face_recognition
        import cv2
    except ImportError as e:
        log.error(f"Missing dependency: {e}")
        return AuthResult.CAMERA_ERROR

    # Load enrolled face encodings
    known_encodings = load_encodings(username)
    if not known_encodings:
        return AuthResult.NO_ENCODINGS

    # Open camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        log.error(f"Cannot open camera at index {CAMERA_INDEX}")
        return AuthResult.CAMERA_ERROR

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if progress_callback:
        progress_callback("scanning", {})

    start_time = time.time()
    frame_count = 0
    result = AuthResult.TIMEOUT

    try:
        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > TIMEOUT_SECONDS:
                log.info("Face unlock timed out")
                result = AuthResult.TIMEOUT
                break

            ret, frame = cap.read()
            if not ret:
                log.warning("Failed to read camera frame")
                time.sleep(0.1)
                continue

            frame_count += 1

            # Process every 2nd frame for performance
            if frame_count % 2 != 0:
                continue

            # Convert BGR (OpenCV) → RGB (face_recognition)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame = np.ascontiguousarray(rgb_frame, dtype=np.uint8)

            # Detect face locations (use 'hog' for CPU, 'cnn' for GPU)
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")

            if not face_locations:
                log.debug("No face detected in frame")
                if progress_callback:
                    progress_callback("no_face", {"elapsed": elapsed})
                continue

            # Encode detected faces
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=2, model="large")

            for face_encoding in face_encodings:
                # Compare with known encodings
                distances = face_recognition.face_distance(known_encodings, face_encoding)
                min_distance = np.min(distances)
                matches = face_recognition.compare_faces(
                    known_encodings, face_encoding,
                    tolerance=CONFIDENCE_THRESHOLD
                )

                log.debug(f"Min distance: {min_distance:.3f}, Threshold: {CONFIDENCE_THRESHOLD}")

                if any(matches):
                    confidence = 1.0 - min_distance
                    log.info(f"Face MATCHED! Confidence: {confidence:.1%}")
                    if progress_callback:
                        progress_callback("success", {"confidence": confidence})
                    result = AuthResult.MATCH
                    break
                else:
                    log.debug(f"Face found but not matched (distance={min_distance:.3f})")
                    if progress_callback:
                        progress_callback("no_match", {"distance": min_distance})

            if result == AuthResult.MATCH:
                break

    finally:
        cap.release()

    return result

# ─── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Face Unlock Engine")
    parser.add_argument("--user", default=os.environ.get("USER", "root"),
                        help="Username to authenticate")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS,
                        help="Timeout in seconds")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD,
                        help="Match confidence threshold (lower = stricter)")
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX,
                        help="Camera device index")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    os.environ["FACE_UNLOCK_TIMEOUT"] = str(args.timeout)
    os.environ["FACE_UNLOCK_THRESHOLD"] = str(args.threshold)
    os.environ["FACE_UNLOCK_CAMERA"] = str(args.camera)

    def show_progress(state, data):
        msgs = {
            "scanning": "🔍 Scanning for face...",
            "no_face":  f"👀 Looking... ({data.get('elapsed', 0):.1f}s)",
            "no_match": f"❌ Face not matched (distance={data.get('distance', 0):.3f})",
            "success":  f"✅ Face matched! ({data.get('confidence', 0):.1%} confidence)",
        }
        print(msgs.get(state, state), file=sys.stderr)

    print(f"Authenticating user: {args.user}", file=sys.stderr)
    result = authenticate(args.user, progress_callback=show_progress)

    print(f"Result: {result.value}", file=sys.stderr)

    if result == AuthResult.MATCH:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
