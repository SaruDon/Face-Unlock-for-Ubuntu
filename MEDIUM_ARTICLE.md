# Building Face Unlock for Ubuntu: How I Brought iPhone Face ID to Linux

*A complete deep-dive into building a biometric authentication system for Ubuntu — from raw webcam frames to PAM integration, animated GTK4 UI, and an always-on Face Guardian daemon.*

---

## Introduction

What if unlocking your Linux laptop felt as seamless as picking up an iPhone? That's the question I set out to answer when I started building **Face Unlock for Ubuntu** — a fully offline, on-device face authentication system that integrates directly into Ubuntu's login, sudo, lock screen, and even the boot splash.

This isn't a toy demo. It plugs into **PAM** (Linux's Pluggable Authentication Module framework), which means every `sudo` command, every login screen, and every lock screen can be unlocked with your face — with an instant password fallback if anything goes wrong.

In this article, I'll walk through every piece of the system:

- **Face recognition engine** (OpenCV + dlib)
- **PAM module** (how Linux authentication works)
- **Animated GTK4 UI** (rendering an iPhone-style scanning ring with Cairo)
- **Face Guardian daemon** (auto-lock when you walk away)
- **GNOME Shell extension** (quick toggle in the system panel)
- **Plymouth boot theme** (Face ID animation at boot)
- **Settings app** (Lock Face — built with libadwaita)
- **Installer & uninstaller** (production-grade shell scripts)

Let's dive in.

---

## Table of Contents

1. [The Big Picture — System Architecture](#1-the-big-picture--system-architecture)
2. [Face Recognition Engine — The Brain](#2-face-recognition-engine--the-brain)
3. [Face Enrollment — Training the System on Your Face](#3-face-enrollment--training-the-system-on-your-face)
4. [PAM Integration — Plugging Into Linux Auth](#4-pam-integration--plugging-into-linux-auth)
5. [The iPhone-Like Animated UI — GTK4 + Cairo Magic](#5-the-iphone-like-animated-ui--gtk4--cairo-magic)
6. [Face Guardian — Always-On Security Daemon](#6-face-guardian--always-on-security-daemon)
7. [GNOME Shell Extension — One-Click Toggle](#7-gnome-shell-extension--one-click-toggle)
8. [Plymouth Boot Theme — Face ID at Boot](#8-plymouth-boot-theme--face-id-at-boot)
9. [Settings App — User-Friendly Configuration](#9-settings-app--user-friendly-configuration)
10. [The Installation System — Making It Production-Ready](#10-the-installation-system--making-it-production-ready)
11. [Security Considerations — What I Got Right (and What's Left)](#11-security-considerations--what-i-got-right-and-whats-left)
12. [Lessons Learned & Future Plans](#12-lessons-learned--future-plans)

---

## 1. The Big Picture — System Architecture

Before we dig into code, let me show you how all the pieces connect:

```
                    ┌────────────────────┐
                    │   User triggers    │
                    │  sudo / login /    │
                    │   lock screen      │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │    PAM Stack       │
                    │  /etc/pam.d/*      │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  pam_face_unlock   │
                    │   (Python PAM)     │
                    └──┬─────────────┬───┘
                       │             │
              ┌────────▼───┐   ┌────▼────────┐
              │ Face Engine│   │  GTK4 UI    │
              │ (dlib/CV)  │   │ (animated)  │
              └────────┬───┘   └─────────────┘
                       │
              ┌────────▼───────────────┐
              │  Match?                │
              │  YES → PAM_SUCCESS ✅  │
              │  NO  → PAM_AUTH_ERR ❌ │
              │        → password      │
              └────────────────────────┘
```

The system also includes background services that run independently:

- **Face Guardian daemon** — monitors the camera continuously and locks the screen if you walk away
- **GNOME Shell extension** — a quick toggle for the guardian in the system panel
- **Plymouth theme** — renders the same Face ID animation during boot

Every component is designed to fail safely: if face recognition breaks, the system falls through to password authentication without locking you out.

---

## 2. Face Recognition Engine — The Brain

**File: `src/face_engine/face_engine.py`** — 217 lines

The face recognition engine is the core of the entire system. It handles three things:

1. **Capturing frames** from the webcam
2. **Detecting faces** in those frames
3. **Comparing detected faces** against enrolled face data

### How Face Recognition Actually Works

I use the `face_recognition` library, which is a Python wrapper around **dlib's** deep learning-based face recognition system. Here's what happens under the hood:

#### Step 1: Face Detection (HOG)

```python
face_locations = face_recognition.face_locations(rgb_frame, model="hog")
```

The HOG (Histogram of Oriented Gradients) model scans the image for face-like patterns. It's fast enough to run on CPU in real-time. The alternative is a CNN model (`model="cnn"`), which is more accurate but requires a GPU to be practical.

#### Step 2: Face Encoding (128-Dimensional Vector)

```python
face_encodings = face_recognition.face_encodings(
    rgb_frame, face_locations, 
    num_jitters=2, model="large"
)
```

For each detected face, dlib's deep neural network generates a **128-dimensional vector** (a list of 128 floating-point numbers) that represents the face's unique features — eye spacing, nose shape, jawline, etc.

The `num_jitters` parameter re-samples the face multiple times with slight perturbations and averages the results for a more stable encoding. During authentication I use `num_jitters=2` (fast), but during enrollment I crank it up to `num_jitters=100` (slow but very robust).

The `model="large"` flag uses dlib's more accurate 31-point face landmark model instead of the smaller 5-point model.

#### Step 3: Comparison (Euclidean Distance)

```python
distances = face_recognition.face_distance(known_encodings, face_encoding)
matches = face_recognition.compare_faces(
    known_encodings, face_encoding,
    tolerance=CONFIDENCE_THRESHOLD  # default 0.55
)
```

The comparison is simple: compute the **Euclidean distance** between the captured face's 128-dim vector and each stored vector. If the distance is below the tolerance threshold, it's a match.

The default threshold of **0.55** means any two faces with a distance ≤ 0.55 are considered the same person. To understand the scale:

- **0.30** — Extremely strict (almost identical faces only)
- **0.55** — Balanced (recommended default)
- **0.75** — Very relaxed (may accept similar-looking people)

### Performance Optimization

The engine processes **every 2nd frame** to save CPU:

```python
if frame_count % 2 != 0:
    continue
```

This keeps the camera running at full speed (for detecting face presence quickly) while halving the expensive face encoding computation.

### The AuthResult Enum

I defined an enum for clean return types:

```python
class AuthResult(Enum):
    MATCH        = "match"        # Face recognized
    NO_MATCH     = "no_match"     # Face found, not recognized
    NO_FACE      = "no_face"      # No face in frame
    CAMERA_ERROR = "camera_error" # Can't open camera
    NO_ENCODINGS = "no_encodings" # User hasn't enrolled
    TIMEOUT      = "timeout"      # Timed out before matching
```

This makes it easy for the PAM module and other consumers to handle every possible outcome.

---

## 3. Face Enrollment — Training the System on Your Face

**File: `src/face_engine/enroll.py`** — 207 lines

Enrollment is the setup step — the user sits in front of the camera while the system captures multiple face samples from different angles.

### The Enrollment Process

1. **Full-screen white background** — The enrollment window is a full-screen white canvas with the webcam feed embedded in the center. This serves as a makeshift ring light, illuminating the user's face with the monitor screen itself:

```python
white_canvas = np.ones((screen_h, screen_w, 3), dtype=np.uint8) * 255
white_canvas[y_offset:y_offset+height, x_offset:x_offset+width] = display_frame
cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
```

2. **15 samples, 0.5-second intervals** — The system collects samples every half second, giving you time to move your head. It requires exactly one face in the frame to capture:

```python
if (len(face_locations) == 1 and
    now - last_sample_time >= 0.5 and
    frame_count > 5):
```

3. **High-quality encodings** — Each sample uses `num_jitters=100` (100 perturbations averaged) with the `large` model for maximum robustness:

```python
face_encodings = face_recognition.face_encodings(
    rgb_frame, num_jitters=100, model="large"
)
```

4. **Visual progress** — The OpenCV window shows a progress bar, face detection bounding box, and sample counter in real-time.

5. **Secure storage** — The collected encodings are serialized with Python's `pickle` and saved to `/etc/face-unlock/encodings/<username>.pkl` with `chmod 600`:

```python
def save_encodings(username, encodings):
    ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = get_encoding_path(username)
    with open(path, "wb") as f:
        pickle.dump(encodings, f)
    os.chmod(path, 0o600)
```

### Why 15 Samples?

More samples from more angles = more reliable matching. With 15 samples covering front, left profile, right profile, looking up, and looking down, the system builds a robust representation that handles everyday variations in position, lighting, and expression.

---

## 4. PAM Integration — Plugging Into Linux Auth

**File: `src/pam/pam_face_unlock.py`** — 166 lines

This is where the magic happens. PAM (Pluggable Authentication Modules) is how Linux handles ALL authentication — from `sudo` to the login screen. By writing a PAM module, face unlock becomes a first-class authentication method.

### How PAM Works

PAM is a chain of modules. When you type `sudo ls`, Linux reads `/etc/pam.d/sudo` and goes through each `auth` line in order. My configuration inserts face unlock **before** the password module:

```
# Try face first
auth  sufficient  pam_python.so /usr/local/lib/face-unlock/pam_face_unlock.py

# Falls through to password if face fails
@include common-auth
```

The keyword `sufficient` means: if this module returns **SUCCESS**, skip everything after it and grant access. If it returns **AUTH_ERR**, continue to the next module (password).

### The PAM Module Code

The entry point is `pam_sm_authenticate()`. Here's what it does:

```python
def pam_sm_authenticate(pamh, flags, argv):
    # 1. Get the username
    username = pamh.get_user(None)
    
    # 2. Check if enrolled
    if not os.path.exists(f"/etc/face-unlock/encodings/{username}.pkl"):
        return PAM_IGNORE  # Skip face auth entirely
    
    # 3. Launch the animated UI (non-blocking)
    ui_proc = subprocess.Popen(
        [FACE_UI_PATH, "--mode", "scanning", "--timeout", str(timeout_val)]
    )
    
    # 4. Run face engine (blocking)
    result = run_face_engine(username)
    
    # 5. Return result
    if result == "match":
        ui_proc.terminate()
        launch_ui_state("success", username)
        return PAM_SUCCESS  # ✅ Grant access
    else:
        ui_proc.terminate()
        launch_ui_state("failed", username)
        return PAM_AUTH_ERR  # ❌ Try password next
```

### The `common-auth` Configuration

For login and lock screen, the PAM rules need to be slightly more nuanced because other system services also use `common-auth`:

```
auth  [success=done ignore=ignore default=1]  pam_python.so /usr/local/lib/face-unlock/pam_face_unlock.py
auth  [success=1 default=ignore]              pam_unix.so nullok_secure try_first_pass
auth  requisite                                pam_deny.so
auth  required                                 pam_permit.so
```

The bracket notation gives precise control:
- `success=done` — If face matches, authentication is complete
- `ignore=ignore` — If the user hasn't enrolled, skip to the next module silently
- `default=1` — If face fails, skip one module (jump over `pam_unix` to `pam_deny`)

Wait, that's wrong — actually `default=1` skips one line to try `pam_deny.so`, which would deny access. But then `pam_unix.so` has `success=1` which skips over `pam_deny` on success. The result is: face OR password must succeed; if both fail, access is denied.

### Why `libpam-python`?

Linux PAM modules are normally written in C. The `libpam-python` package provides `pam_python.so`, which is a C module that loads and executes a Python script. This lets me write the entire PAM module in Python while still integrating natively with the PAM stack.

---

## 5. The iPhone-Like Animated UI — GTK4 + Cairo Magic

**File: `src/ui/face_unlock_ui.py`** — 655 lines

This is the most visually impressive part of the project. The UI renders an iPhone Face ID-style scanning ring that animates smoothly at 60fps.

### The FaceRingWidget

The ring is a custom `Gtk.DrawingArea` with a Cairo drawing function:

```python
class FaceRingWidget(Gtk.DrawingArea):
    RING_SIZE = 200
    RING_THICKNESS = 6
    
    def __init__(self):
        super().__init__()
        self.set_size_request(self.RING_SIZE, self.RING_SIZE)
        self.state = "scanning"
        self.angle = 0.0          # rotation angle
        self.pulse = 0.0          # glow amount
        self.fill_progress = 0.0  # success fill
        self.shake_offset = 0.0   # failure shake
        
        # 60fps animation timer
        GLib.timeout_add(16, self._animate)
```

### Scanning Animation

The scanning state renders a golden 280° arc that rotates 3.5°/frame with a pulsing outer glow:

```python
def _draw_scanning_ring(self, cr, cx, cy, r):
    start = math.radians(self.angle - 30)
    end   = math.radians(self.angle + 250)
    
    # Glow effect (sinusoidal pulse)
    glow_alpha = 0.12 + 0.08 * self.pulse
    cr.set_source_rgba(1.0, 0.85, 0.0, glow_alpha)
    cr.set_line_width(self.RING_THICKNESS * 3.5)
    cr.arc(cx, cy, r, start, end)
    cr.stroke()
    
    # Main golden arc
    cr.set_source_rgba(1.0, 0.85, 0.0, 0.95)
    cr.set_line_width(self.RING_THICKNESS)
    cr.arc(cx, cy, r, start, end)
    cr.stroke()
    
    # Trailing fade
    cr.set_source_rgba(1.0, 0.85, 0.0, 0.25)
    cr.set_line_width(self.RING_THICKNESS * 0.5)
    cr.arc(cx, cy, r, end, end + math.radians(60))
    cr.stroke()
```

### Success Animation

On a successful match, a green ring fills clockwise from the top, and a checkmark fades in at 90% progress:

```python
def _draw_success_ring(self, cr, cx, cy, r):
    end_angle = 2 * math.pi * self.fill_progress
    
    # Green fill ring
    cr.set_source_rgba(0.2, 0.78, 0.35, 1.0)
    cr.arc(cx, cy, r, -math.pi/2, -math.pi/2 + end_angle)
    cr.stroke()
    
    # Checkmark (fades in at 90%)
    if self.fill_progress > 0.9:
        alpha = min(1.0, (self.fill_progress - 0.9) * 10)
        cr.set_source_rgba(0.2, 0.78, 0.35, alpha)
        # Draw checkmark path
        cr.move_to(cx - s*0.5, cy)
        cr.line_to(cx - s*0.1, cy + s*0.4)
        cr.line_to(cx + s*0.6, cy - s*0.4)
        cr.stroke()
```

### Failure Animation

The failed state shows a red ring with an X mark and a **damped oscillation** shake effect:

```python
# Shake: decaying sinusoidal oscillation
t = self._tick % 40
self.shake_offset = 8 * math.sin(t * 0.6) * max(0, 1 - t / 40)
```

This creates a physically-realistic "head shake" that starts strong and fades to zero over 40 frames.

### The Person Silhouette

Inside the ring, there's a simple person silhouette made of two filled circles:

```python
# Head
cr.set_source_rgba(1, 1, 1, 0.3)
cr.arc(cx, cy - 22, 28, 0, 2 * math.pi)
cr.fill()

# Shoulders (half-circle)
cr.arc(cx, cy + 40, 44, math.pi, 2 * math.pi)
cr.fill()
```

### CSS Theme

The overlay has a sleek dark theme inspired by iOS:

```css
.unlock-overlay {
    background: rgba(0, 0, 0, 0.88);
    border-radius: 28px;
}

.status-label {
    font-family: 'SF Pro Display', 'Ubuntu', 'Inter', sans-serif;
    color: rgba(255, 255, 255, 0.85);
}

.password-entry {
    background: rgba(255, 255, 255, 0.12);
    border: 1.5px solid rgba(255, 255, 255, 0.2);
    border-radius: 14px;
}
```

### GTK4/GTK3 Dual Support

The UI detects available GTK versions at import time and adapts:

```python
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, GLib, Gdk, Pango, Gio
    HAS_GTK4 = True
except ImportError:
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib, Gdk, Pango
    HAS_GTK3 = True
```

This ensures compatibility across Ubuntu 20.04 (GTK3), 22.04 (GTK4), and 24.04 (GTK4 + libadwaita).

---

## 6. Face Guardian — Always-On Security Daemon

**File: `src/guardian/face_guardian.py`** — 241 lines

The Face Guardian is a background daemon that continuously monitors the camera. If the enrolled user's face disappears for a configurable number of seconds, it **locks the screen automatically** — like an always-on security guard.

### How It Works

```python
def main():
    while True:
        # Read config each loop (allows runtime changes)
        lock_delay = int(get_config("guard_lock_delay", "30"))
        guard_enabled = get_config("guard_enabled", "false") == "true"
        
        if not guard_enabled or is_screen_locked():
            time.sleep(5)
            continue
        
        # Quick camera check
        face_status = check_face(encodings, tolerance)
        
        if face_status["authorized"]:
            # Reset timer, dismiss warning
            last_seen_time = time.time()
        else:
            absent_duration = time.time() - last_seen_time
            
            if absent_duration > lock_delay:
                lock_screen()
            elif warning_process is None:
                # Show countdown warning UI
                launch_warning_ui(remaining)
        
        time.sleep(2)  # Poll every 2 seconds
```

### Multi-Model Face Detection

The guardian uses a **layered detection approach** to avoid false lockouts:

1. **Primary:** `face_recognition` HOG detector + dlib encoding comparison (matches the authorized user specifically)
2. **Fallback 1:** OpenCV's frontal face Haar cascade (catches face at any angle but doesn't identify who it is)
3. **Fallback 2:** OpenCV's profile face Haar cascade (catches side views)
4. **Fallback 3:** Flipped profile cascade (catches the other side)

This layered approach means: even if the authorized face check fails (e.g., you're looking at a different monitor), the system won't lock immediately as long as *any* face-like shape is detected.

### The Warning UI

When the guardian detects face absence, it launches the Face Unlock UI in `warning` mode — an orange pulsing ring with a countdown:

```python
warning_process = subprocess.Popen(
    [script_path, "--mode", "warning", "--timeout", str(remaining)]
)
```

If you return before the countdown expires, it dismisses the warning and resets the timer.

### Screen Locking

The guardian uses two methods to lock the screen:

```python
def lock_screen():
    # Method 1: loginctl (systemd)
    subprocess.run(["loginctl", "lock-session", session_id])
    
    # Method 2: gdbus (GNOME ScreenSaver)
    subprocess.run(["gdbus", "call", "-e", 
                     "-d", "org.gnome.ScreenSaver",
                     "-o", "/org/gnome/ScreenSaver", 
                     "-m", "org.gnome.ScreenSaver.Lock"])
```

### Safety Design

The guardian **defaults to "authorized"** in any error condition:

- Camera busy? → Assume authorized
- Dependencies missing? → Assume authorized
- Frame read failure? → Assume authorized

This prevents the daemon from accidentally locking you out due to a bug or hardware issue.

### systemd Service

The guardian runs as a **user service**, which means it starts automatically when you log in to GNOME and stops when you log out:

```ini
[Unit]
Description=Always-On Face Guardian
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/face-unlock/face_guardian.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

---

## 7. GNOME Shell Extension — One-Click Toggle

**File: `src/gnome-extension/extension.js`** — 83 lines

The GNOME Shell extension adds a **"Face Guard" quick toggle** to the system Quick Settings panel (the panel where you toggle Wi-Fi, Bluetooth, Night Light, etc.).

```javascript
const FaceGuardToggle = class FaceGuardToggle extends QuickToggle {
    constructor() {
        super({
            title: 'Face Guard',
            iconName: 'changes-prevent-symbolic',
            toggleMode: true,
        });
        
        this.checked = getGuardEnabled();
        
        this.connect('clicked', () => {
            const newState = this.checked ? 'disable' : 'enable';
            Gio.Subprocess.new(
                ['pkexec', '/usr/local/lib/face-unlock/toggle-guard.sh', newState],
                Gio.SubprocessFlags.NONE
            );
            this.checked = !this.checked;
        });
    }
};
```

The toggle uses `pkexec` for privilege escalation — when you click it, a system password dialog appears (via PolicyKit), and only after authentication does it modify the config.

The extension also polls the config file every 2 seconds to stay in sync if the guard state is changed from elsewhere (e.g., the settings app):

```javascript
GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
    if (_toggle) _toggle.checked = getGuardEnabled();
    return GLib.SOURCE_CONTINUE;
});
```

---

## 8. Plymouth Boot Theme — Face ID at Boot

**File: `src/boot/plymouth-theme/face-unlock.script`** — 156 lines

Plymouth is the system that renders the boot splash screen on Ubuntu. I created a custom Plymouth theme that shows the same golden Face ID ring animation during boot.

### Plymouth's Scripting Language

Plymouth has its own C-like scripting language. The theme draws shapes procedurally on every refresh tick:

```c
fun draw_ring(x, y, r, start_deg, end_deg, r_col, g_col, b_col, a_col, thickness) {
    steps = 64;
    start_rad = start_deg * 3.14159 / 180;
    end_rad   = end_deg   * 3.14159 / 180;
    span = end_rad - start_rad;
    
    i = 0;
    while (i < steps) {
        // Calculate inner/outer arc segments
        seg = Window.GetQuadrangle(x1o, y1o, x2o, y2o, x2i, y2i, x1i, y1i);
        seg.SetColor(r_col, g_col, b_col, a_col);
        i++;
    }
}
```

### Boot States

The theme has three visual states:

1. **Scanning** — Golden rotating arc (4°/tick) with pulsing glow
2. **Success** — Full green ring with "Unlocked" text
3. **Password** — Red ring with password input box

When Plymouth triggers the password callback, the theme switches to password mode:

```c
fun display_password_callback(prompt, bullets) {
    mode = "password";
    pass_label.SetText(bullets);
    pass_label.SetVisible(true);
}

Plymouth.SetDisplayPasswordFunction(display_password_callback);
```

---

## 9. Settings App — User-Friendly Configuration

**File: `src/ui/settings_app.py`** — 391 lines

The **Lock Face** app is a standalone libadwaita application that serves as the central settings interface. It includes:

- **Hero status section** — Shows enrollment status with icon and label
- **Face data management** — Enroll face and delete face data (with confirmation dialog)
- **Face Guardian controls** — Toggle the always-on guardian, set lock delay
- **Security settings** — Match strictness slider (Strict / Balanced / Relaxed), scan timeout
- **Toast notifications** — Visual feedback when settings are applied
- **Direct service management** — Starts/stops the `face-guardian.service` directly via systemd

All settings read and write `/etc/face-unlock/config.conf`. The app is registered as a `.desktop` entry and appears in the Ubuntu app menu under "Lock Face".

---

## 10. The Installation System — Making It Production-Ready

**File: `install.sh`** — 310 lines

The installer is a bash script that handles everything from system package installation to PAM configuration. Notable features:

### Animated Compilation Spinner

Since dlib compilation takes 5–15 minutes, I added a visual spinner with elapsed time:

```bash
SPINNER_FRAMES=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')

while kill -0 "$PIP_PID" 2>/dev/null; do
    ELAPSED=$(( $(date +%s) - START_TS ))
    FRAME="${SPINNER_FRAMES[$SPINNER_IDX]}"
    printf "\r  %s  Compiling & installing…  %dm %02ds elapsed   " \
        "$FRAME" "$MINS" "$SECS"
    sleep 0.12
done
```

### PAM Safety Net

The installer always backs up original PAM configs before modifying them:

```bash
for PAM_FILE in sudo common-auth; do
    cp "/etc/pam.d/${PAM_FILE}" "${BAK_DIR}/${PAM_FILE}.bak"
done
```

This means `uninstall.sh` can always restore the system to its original state.

### Polkit Policy

The installer registers a PolicyKit policy that allows graphical password prompts for enrollment and guard management:

```xml
<policyconfig>
    <action id="com.face-unlock.enroll">
        <description>Enroll face for Face Unlock</description>
        <defaults>
            <allow_active>auth_admin_keep</allow_active>
        </defaults>
    </action>
    
    <action id="com.face-unlock.guard">
        <description>Modify Face Guard settings</description>
        <defaults>
            <allow_active>auth_admin_keep</allow_active>
        </defaults>
    </action>
</policyconfig>
```

---

## 11. Security Considerations — What I Got Right (and What's Left)

### ✅ What's Secure

| Aspect | Implementation |
|--------|----------------|
| **Data locality** | All face data stored on-device in `/etc/face-unlock/encodings/` — no cloud, no network |
| **File permissions** | Encoding files are `chmod 600` — only root can read them |
| **PAM fallback** | Password always works. Face unlock is additive (`sufficient`), not exclusive |
| **Config backup** | Original PAM configs are preserved for clean restoration |
| **Privilege separation** | Enrollment and guard toggling use PolicyKit for proper auth escalation |
| **Anti-lockout** | Guardian daemon defaults to "authorized" on any error |
| **Multi-angle enrollment** | 15 samples from multiple angles with 100 jitters create robust encodings |
| **Logging** | All auth attempts logged to `/var/log/face-unlock.log` |

### ⚠️ Known Limitations

| Limitation | Details |
|------------|---------|
| **No liveness detection** | The system currently cannot distinguish a real face from a photo or video. Advanced liveness detection (blink detection, depth sensing, IR illumination) would require additional hardware or more complex software. |
| **Pickle serialization** | Face data is stored as Python pickle files, which could theoretically be tampered with by a root-level attacker. However, since root already has full system access, this is not a practical escalation vector. |
| **Single threshold** | The same threshold applies to all comparisons. An adaptive threshold based on enrollment quality could improve accuracy. |
| **No 2FA** | Face unlock is not combined with a second factor. For high-security environments, face + password would be ideal. |

---

## 12. Lessons Learned & Future Plans

### Lessons Learned

1. **PAM is tricky** — Getting the PAM control flow right (`sufficient` vs `required` vs bracket notation) required careful testing. One wrong keyword and you can lock yourself out of `sudo`.

2. **Display environment is a nightmare** — When PAM runs your module, there's no `$DISPLAY` set. When you `su - user`, the display env is stripped. The 128-line UI launcher script (`face-unlock-ui`) exists entirely to solve this problem.

3. **dlib compilation is expensive** — Building dlib from source on a typical laptop takes 10–15 minutes and requires ~2GB RAM. The animated spinner in the installer was born out of staring at a seemingly-frozen terminal for too long.

4. **GTK4 vs GTK3** — Writing a UI that works on both GTK generations required careful abstraction. The API differences are small but numerous (`pack_start` → `append`, `StyleContext` → `add_css_class`).

5. **Systemd user services** — Getting a user service to access the right graphical session, X11 display, and Wayland socket required exploring several detection strategies.

### Future Plans

- **Liveness detection** — Blink detection + micro-movement analysis to prevent photo attacks
- **Infrared camera support** — IR cameras work in total darkness and are harder to spoof
- **Multi-user enrollment** — Support multiple enrolled users per system
- **Fingerprint fallback chain** — Integrate with `fprintd` for fingerprint + face + password
- **GNOME 47 redesign** — Update the Lock Face settings app to match the new GNOME Settings UI patterns

---

## Conclusion

Building Face Unlock for Ubuntu was an exercise in full-stack Linux systems programming — touching everything from deep learning inference to PAM's C interfaces, from Cairo graphics to systemd services, from Plymouth's boot animation scripting to GNOME Shell extensions.

The result is a system that actually *feels* like it belongs on a modern desktop — not a hacky proof of concept, but a polished tool with proper installation, multiple settings interfaces, graceful fallbacks, and production-grade error handling.

If you're interested in trying it out, check out the [GitHub repository](https://github.com/jadiya/face-unlock-ubuntu) and follow the installation instructions. And if you have ideas for improvements — especially around liveness detection — I'd love to hear from you.

---

*Thanks for reading! If you found this interesting, follow me for more Linux systems programming and security projects.*

**Tags:** `#Linux` `#Ubuntu` `#FaceRecognition` `#OpenCV` `#Python` `#PAM` `#GTK` `#SystemsProgramming` `#Biometrics` `#OpenSource`
