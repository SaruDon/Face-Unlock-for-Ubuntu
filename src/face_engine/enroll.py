#!/usr/bin/env python3
"""
Face Unlock — Enrollment Wizard
Captures multiple face samples and saves encoded data for a user.
Must be run with sudo (writes to /etc/face-unlock/)
"""

import os
import sys
import time
import getpass
import argparse
import logging

# Ensure root can open GTK/Qt windows when running via sudo
if os.geteuid() == 0:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        # Pass the original user's display environment to root
        if "XAUTHORITY" not in os.environ:
            os.environ["XAUTHORITY"] = f"/home/{sudo_user}/.Xauthority"
        
        # In modern GNOME/Wayland setups with Xwayland, it often lives in /run/user/1000/
        uid_out = os.popen(f"id -u {sudo_user}").read().strip()
        if uid_out:
            gdm_xauth = f"/run/user/{uid_out}/gdm/Xauthority"
            if os.path.exists(gdm_xauth) and not os.path.exists(os.environ["XAUTHORITY"]):
                os.environ["XAUTHORITY"] = gdm_xauth

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("enroll")

SAMPLES_NEEDED = 15
CAMERA_INDEX   = int(os.environ.get("FACE_UNLOCK_CAMERA", "0"))

def print_banner():
    print("\n")
    print("  ╔══════════════════════════════════════╗")
    print("  ║       Face Unlock — Enrollment       ║")
    print("  ╚══════════════════════════════════════╝")
    print()

def enroll_user(username: str, camera_idx: int = CAMERA_INDEX) -> bool:
    try:
        import face_recognition
        import cv2
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Run: sudo pip3 install face_recognition opencv-python")
        return False

    from face_engine import save_encodings

    print(f"  👤 Enrolling face for user: {username}")
    print(f"  📷 Using camera: /dev/video{camera_idx}")
    print()
    print("  Instructions:")
    print("  • Look directly at the camera at first")
    print("  • Slowly turn your head SIDE TO SIDE (Profile Views)")
    print("  • Slowly look UP and DOWN")
    print("  • Keep good lighting on your face")
    print("  • Stay within 30–80cm of the camera")
    print()

    input("  Press ENTER when ready to start enrollment... ")

    cap = cv2.VideoCapture(camera_idx)
    if not cap.isOpened():
        print(f"❌ Cannot open camera at index {camera_idx}")
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    collected_encodings = []
    frame_count = 0
    sample_count = 0
    last_sample_time = 0

    print(f"\n  📸 Capturing {SAMPLES_NEEDED} face samples...")
    print()

    window_name = "Face Unlock — Enrollment (press Q to abort)"

    try:
        while sample_count < SAMPLES_NEEDED:
            ret, frame = cap.read()
            if not ret:
                continue

            frame_count += 1
            import numpy as np
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame = np.ascontiguousarray(rgb_frame, dtype=np.uint8)

            # Detect faces
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")

            # Draw UI on frame
            display_frame = frame.copy()
            height, width = frame.shape[:2]

            # Progress bar
            progress = sample_count / SAMPLES_NEEDED
            bar_width = int(width * 0.8)
            bar_x = int(width * 0.1)
            bar_y = height - 40
            cv2.rectangle(display_frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + 20), (40, 40, 40), -1)
            cv2.rectangle(display_frame, (bar_x, bar_y), (bar_x + int(bar_width * progress), bar_y + 20), (0, 200, 100), -1)
            cv2.putText(display_frame, f"Samples: {sample_count}/{SAMPLES_NEEDED}",
                       (bar_x, bar_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            for (top, right, bottom, left) in face_locations:
                # Draw face box
                color = (0, 200, 100) if len(face_locations) == 1 else (0, 165, 255)
                cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
                cv2.putText(display_frame, "Face Detected", (left, top - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Sample every 0.5 seconds when exactly 1 face is visible
            now = time.time()
            if (len(face_locations) == 1 and
                    now - last_sample_time >= 0.5 and
                    frame_count > 5):

                # Use the single-arg form — avoids dlib API version mismatches
                face_encodings = face_recognition.face_encodings(rgb_frame, num_jitters=100, model="large")
                if face_encodings:
                    collected_encodings.append(face_encodings[0])
                    sample_count += 1
                    last_sample_time = now
                    log.info(f"  ✅ Sample {sample_count}/{SAMPLES_NEEDED} captured")

            # Create full white screen to illuminate face
            screen_h, screen_w = 1080, 1920
            white_canvas = np.ones((screen_h, screen_w, 3), dtype=np.uint8) * 255
            
            # Embed frame into center of canvas
            y_offset = (screen_h - height) // 2
            x_offset = (screen_w - width) // 2
            white_canvas[y_offset:y_offset+height, x_offset:x_offset+width] = display_frame

            cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.imshow(window_name, white_canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                print("\n  ❌ Enrollment aborted by user.")
                return False

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if len(collected_encodings) < SAMPLES_NEEDED:
        print(f"\n  ❌ Only captured {len(collected_encodings)} samples. Enrollment failed.")
        return False

    # Save encodings
    print(f"\n  💾 Saving face data...")
    save_encodings(username, collected_encodings)

    print(f"\n  ✅ Enrollment complete! {len(collected_encodings)} samples saved for '{username}'")
    print("  Face unlock is now ready to use.\n")
    return True

def delete_enrollment(username: str) -> bool:
    from face_engine import get_encoding_path
    path = get_encoding_path(username)
    if path.exists():
        path.unlink()
        print(f"✅ Removed face data for '{username}'")
        return True
    else:
        print(f"⚠️  No face data found for '{username}'")
        return False

def main():
    global SAMPLES_NEEDED
    print_banner()
    parser = argparse.ArgumentParser(description="Face Unlock Enrollment")
    parser.add_argument("--user", default=None, help="Username to enroll (default: current user)")
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX, help="Camera device index")
    parser.add_argument("--delete", action="store_true", help="Delete enrolled face for user")
    parser.add_argument("--samples", type=int, default=10, help="Number of samples to capture")
    args = parser.parse_args()

    username = args.user or os.environ.get("SUDO_USER") or getpass.getuser()

    if os.geteuid() != 0:
        print("  ⚠️  This script must be run with sudo.")
        print(f"     Run: sudo python3 enroll.py --user {username}")
        sys.exit(1)

    SAMPLES_NEEDED = args.samples

    if args.delete:
        delete_enrollment(username)
        sys.exit(0)

    success = enroll_user(username, args.camera)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
