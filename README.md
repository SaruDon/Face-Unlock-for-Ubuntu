<p align="center">
  <h1 align="center">🔐 Face Unlock for Ubuntu</h1>
  <p align="center">
    <strong>iPhone-style face authentication for Ubuntu Linux — unlock sudo, login, lock screen, and boot with your face.</strong>
  </p>
  <p align="center">
    Built with <b>OpenCV</b> · <b>dlib</b> · <b>face_recognition</b> · <b>GTK4 / libadwaita</b> · <b>PAM</b> · <b>Plymouth</b>
  </p>
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [System Requirements](#-system-requirements)
- [Installation](#-installation)
- [Face Enrollment](#-face-enrollment)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Module Deep-Dive](#-module-deep-dive)
  - [Face Recognition Engine](#1-face-recognition-engine)
  - [PAM Integration](#2-pam-integration)
  - [Animated GTK4 UI](#3-animated-gtk4-ui)
  - [Face Guardian Daemon](#4-face-guardian-daemon)
  - [GNOME Shell Extension](#5-gnome-shell-extension)
  - [Settings App (Lock Face)](#6-settings-app-lock-face)
  - [Plymouth Boot Theme](#7-plymouth-boot-theme)
  - [UI Launcher Script](#8-ui-launcher-script)
- [Configuration](#%EF%B8%8F-configuration)
- [Authentication Flow](#-authentication-flow)
- [Installed Files & Paths](#-installed-files--paths)
- [Security Model](#-security-model)
- [Uninstallation](#%EF%B8%8F-uninstallation)
- [Troubleshooting](#-troubleshooting)
- [Tech Stack](#-tech-stack)
- [License](#-license)

---

## 🌟 Overview

**Face Unlock for Ubuntu** brings Apple Face ID–like biometric authentication to Ubuntu desktops. It integrates directly into Linux's **PAM (Pluggable Authentication Module)** stack so that any authentication prompt — `sudo`, login screen, lock screen, or even the boot splash — can be unlocked by simply looking at your webcam.

The project is **fully offline** — no cloud services, no internet connection needed. Face data is encoded using **dlib's 128-dimensional face embedding model**, stored locally as `.pkl` files, and compared on-device every time authentication is attempted.

When face recognition is triggered, a gorgeous **iPhone-like animated UI** renders a golden scanning ring (built with GTK4 + Cairo), transitions to a green checkmark on success, or red X on failure, and gracefully falls back to a standard password prompt.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 📷 **Webcam Authentication** | Works with any USB or built-in webcam. Configurable camera index via environment variable. |
| 🔑 **sudo Unlock** | Face replaces password for `sudo` commands. Transparent PAM integration — no command changes needed. |
| 🖥️ **Login & Lock Screen** | Face unlock for GDM, LightDM, and GNOME lock screen via `common-auth` PAM module. |
| 🚀 **Boot Unlock** | Custom Plymouth theme renders a Face ID scanning animation during system boot. |
| 📱 **iPhone-like Animated UI** | GTK4 + Cairo animated overlay — golden scanning ring, green success fill, red shake failure, orange warning pulse. |
| 🔒 **Password Fallback** | If face fails or times out, password prompt appears immediately. System is never locked out. |
| 👁️ **Face Guardian** | Background daemon continuously monitors camera; locks screen when authorized face disappears for N seconds. |
| ⚡ **GNOME Quick Toggle** | GNOME Shell extension adds a "Face Guard" toggle to the system Quick Settings panel. |
| ⚙️ **Settings App** | Full-featured `Lock Face` settings app built with libadwaita — manage enrollment, guardian, and security. |
| 🎨 **Polkit Integration** | Enrollment and guard toggling use PolicyKit for secure privilege escalation with graphical password prompts. |
| 🧩 **Multi-Ubuntu Support** | Tested on Ubuntu 20.04, 22.04, and 24.04. Graceful GTK4/GTK3 fallback built-in. |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Ubuntu System                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┐    ┌─────────────────┐                    │
│   │  sudo / login │───▶│   PAM Stack      │                    │
│   │   (any auth)  │    │  /etc/pam.d/*   │                    │
│   └──────────────┘    └──────┬──────────┘                    │
│                              │                               │
│                    ┌─────────▼──────────┐                    │
│                    │  pam_python.so     │                    │
│                    │  → pam_face_unlock │                    │
│                    └────────┬───────────┘                    │
│                             │                                │
│              ┌──────────────┼───────────────┐                │
│              │              │               │                │
│    ┌─────────▼───────┐ ┌───▼────────┐ ┌───▼──────┐         │
│    │  Face Engine    │ │  GTK4 UI   │ │ Password │         │
│    │  (OpenCV+dlib)  │ │  (animated)│ │ Fallback │         │
│    │  face_engine.py │ │  *.py      │ │ pam_unix │         │
│    └─────────────────┘ └────────────┘ └──────────┘         │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │          Background Services & Extensions             │  │
│   │                                                        │  │
│   │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐   │  │
│   │  │ Face        │  │ GNOME Shell  │  │ Plymouth   │   │  │
│   │  │ Guardian    │  │ Extension    │  │ Boot Theme │   │  │
│   │  │ (daemon)    │  │ (quick tile) │  │ (splash)   │   │  │
│   │  └─────────────┘  └──────────────┘  └────────────┘   │  │
│   └──────────────────────────────────────────────────────┘  │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │              Configuration & Settings                 │  │
│   │                                                        │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│   │  │ Settings App │  │ GNOME Panel  │  │ config.conf│ │  │
│   │  │ (Lock Face)  │  │ (Preferences)│  │ (file)     │ │  │
│   │  └──────────────┘  └──────────────┘  └────────────┘ │  │
│   └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 💻 System Requirements

| Requirement | Minimum |
|-------------|---------|
| **OS** | Ubuntu 20.04+  (22.04 / 24.04 recommended) |
| **Camera** | Any USB or built-in webcam |
| **Desktop** | GNOME (for full integration; others partially supported) |
| **Python** | Python 3.8+ (ships with Ubuntu) |
| **Disk** | ~500 MB (dlib compilation) |
| **RAM** | 2 GB+ recommended (dlib model loads into memory) |
| **Privileges** | `sudo` access required for installation |

---

## 📦 Installation

```bash
# 1. Clone or download the project
git clone https://github.com/jadiya/face-unlock-ubuntu.git
cd face-unlock-ubuntu/

# 2. Run the installer (takes ~10 minutes — compiles dlib from source)
sudo bash install.sh

# 3. Enroll your face
sudo bash enroll.sh

# 4. Test it!
sudo ls /root     # ← should trigger face unlock UI instead of password
```

### What the Installer Does

The `install.sh` script performs these steps **automatically**:

| Step | Description |
|------|-------------|
| **1. System Detection** | Validates Ubuntu 20.04+ and verifies root access |
| **2. Create Directories** | Creates `/usr/local/lib/face-unlock/`, `/etc/face-unlock/encodings/`, backups dir, etc. |
| **3. System Packages** | Installs `python3-pip`, `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `libpam-python`, `cmake`, `build-essential`, `libopencv-dev`, `python3-opencv`, `python3-numpy`, `libdlib-dev`, `libboost-python-dev`, `plymouth`, `policykit-1`, and more |
| **4. Python Packages** | Installs `face_recognition` and `opencv-python` via pip (compiles dlib with a visual spinner) |
| **5. Copy Library Files** | Copies `face_engine.py`, `enroll.py`, `pam_face_unlock.py`, `face_unlock_ui.py`, `face_guardian.py`, `toggle-guard.sh` to `/usr/local/lib/face-unlock/` |
| **6. PAM Module** | Installs `pam_face_unlock.py` to `/lib/security/` |
| **7. PAM Configuration** | Backs up original `/etc/pam.d/sudo` and `/etc/pam.d/common-auth`, replaces them with face-unlock-aware versions |
| **8. Plymouth Theme** | Installs the Face ID boot animation to `/usr/share/plymouth/themes/face-unlock/` |

| **10. Polkit Policy** | Installs `com.face-unlock.policy` for secure enrollment and guard toggling |
| **11. GNOME Extension & Guardian** | Installs the Face Guard quick toggle extension and systemd user service file |
| **12. Default Config** | Writes `/etc/face-unlock/config.conf` with sensible defaults |

---

## 👤 Face Enrollment

```bash
sudo bash enroll.sh
```

The enrollment wizard:

1. **Opens the webcam** in a full-screen white-background window (for maximum face illumination)
2. **Detects your face** in real-time using OpenCV's HOG face detector
3. **Captures 15 samples** at 0.5-second intervals as you move your head (straight, left, right, up, down)
4. **Extracts 128-dimensional face encodings** using dlib's deep learning model (`num_jitters=100, model="large"` for maximum accuracy)
5. **Saves encodings** to `/etc/face-unlock/encodings/<username>.pkl` with `chmod 600` permissions

The enrollment window shows a live progress bar and face detection bounding box. Press **Q** or **Esc** to abort.

### Enrollment Parameters

| Parameter | Default | CLI Flag |
|-----------|---------|----------|
| Samples to capture | 15 | `--samples N` |
| Camera index | 0 | `--camera N` |
| Target user | `$SUDO_USER` | `--user NAME` |
| Delete enrolled face | — | `--delete` |

---

## 🚀 Quick Start

### Test the Animated UI (No Auth Needed)

```bash
python3 /usr/local/lib/face-unlock/face_unlock_ui.py --demo
```

Cycles through all UI states: `scanning → success → failed → scanning → password fallback`

### Test Face Recognition

```bash
python3 /usr/local/lib/face-unlock/face_engine.py --user $USER --verbose
```

Shows real-time face detection with distance/confidence output.

### Open Lock Face Settings App

```bash
python3 /usr/local/lib/face-unlock/settings_app.py
```

Or search **"Lock Face"** in the app menu.

---

## 📁 Project Structure

```
Face Unlock for Ubuntu/
│
├── install.sh                  ← System installer (sudo bash install.sh)
├── uninstall.sh                ← Clean uninstaller (sudo bash uninstall.sh)
├── enroll.sh                   ← Face enrollment launcher (sudo bash enroll.sh)
├── face-unlock.desktop         ← .desktop entry for the Lock Face settings app
├── README.md                   ← This file
│
├── src/
│   ├── face_engine/            ← Core face recognition
│   │   ├── face_engine.py      ← Recognition engine (OpenCV + dlib + face_recognition)
│   │   └── enroll.py           ← Face enrollment wizard with live camera preview
│   │
│   ├── pam/                    ← PAM authentication module
│   │   ├── pam_face_unlock.py  ← PAM module (pam_python.so plugin)
│   │   └── pam_configs/
│   │       ├── sudo            ← PAM config for sudo (face first, password fallback)
│   │       └── common-auth     ← PAM config for login/lock screen/su
│   │
│   ├── ui/                     ← User interface components
│   │   ├── face_unlock_ui.py   ← iPhone-like animated GTK4 overlay (Face ID ring)
│   │   ├── face-unlock-ui      ← Bash launcher script (resolves display env)
│   │   └── settings_app.py     ← Lock Face settings app (libadwaita)
│   │
│   ├── guardian/               ← Always-on face monitoring
│   │   ├── face_guardian.py    ← Background daemon — locks screen on face absence
│   │   ├── face-guardian.service ← systemd user service file
│   │   └── toggle-guard.sh     ← Polkit-protected enable/disable script
│   │
│   ├── gnome-extension/        ← GNOME Shell quick settings toggle
│   │   ├── extension.js        ← Quick toggle for Face Guard in system tray
│   │   ├── metadata.json       ← Extension metadata (GNOME Shell 42–47)
│   │   └── stylesheet.css      ← Extension styling
│   │
│   └── boot/                   ← Boot splash integration
│       └── plymouth-theme/
│           ├── face-unlock.plymouth  ← Plymouth theme metadata
│           └── face-unlock.script    ← Plymouth animation script (Face ID ring)
│
├── test_dlib.py                ← Development test scripts
├── test_dlib2.py
├── test_face.py
├── test_profile.py
└── test_profile2.py
```

---

## 🔍 Module Deep-Dive

### 1. Face Recognition Engine

**File:** `src/face_engine/face_engine.py` (217 lines)

The core authentication module. Handles camera capture, face detection, and face comparison.

#### Key Components

| Component | Details |
|-----------|---------|
| **Library** | `face_recognition` (wraps dlib's deep CNN face encoder) |
| **Face Detection** | HOG (Histogram of Oriented Gradients) — fast, CPU-only |
| **Face Encoding** | 128-dimensional embedding vector, `num_jitters=2`, `model="large"` |
| **Comparison** | Euclidean distance + configurable tolerance threshold |
| **Camera** | OpenCV `VideoCapture` at 640×480 @ 30fps |
| **Performance** | Processes every 2nd frame to maintain responsiveness |

#### Authentication Flow (Code Level)

```python
def authenticate(username, progress_callback=None) -> AuthResult:
    # 1. Load enrolled face encodings from /etc/face-unlock/encodings/<user>.pkl
    # 2. Open webcam (index from FACE_UNLOCK_CAMERA env var)
    # 3. Loop until timeout:
    #    a. Read frame, skip every other frame for performance
    #    b. Convert BGR → RGB
    #    c. Detect face locations using HOG model
    #    d. Extract 128-dim face encodings
    #    e. Compare against all stored encodings using face_distance()
    #    f. If any match within tolerance threshold → AuthResult.MATCH
    # 4. On timeout → AuthResult.TIMEOUT
```

#### AuthResult Enum

| Value | Meaning |
|-------|---------|
| `MATCH` | Face recognized — grant access |
| `NO_MATCH` | Face detected but doesn't match enrolled user |
| `NO_FACE` | No face detected in frame |
| `CAMERA_ERROR` | Camera failed to open or read frames |
| `NO_ENCODINGS` | User has no enrolled face data |
| `TIMEOUT` | Scan window expired without a match |

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FACE_UNLOCK_CAMERA` | `0` | Camera device index |
| `FACE_UNLOCK_THRESHOLD` | `0.55` | Match tolerance (lower = stricter) |
| `FACE_UNLOCK_ATTEMPTS` | `20` | Max frames to analyze |
| `FACE_UNLOCK_TIMEOUT` | `8.0` | Seconds before giving up |

---

### 2. PAM Integration

**File:** `src/pam/pam_face_unlock.py` (166 lines)

A Python PAM module loaded by `pam_python.so` (from `libpam-python`). This is the glue between Linux authentication and the face engine.

#### How PAM Works Here

Linux authentication calls go through the PAM stack defined in `/etc/pam.d/`. The module inserts itself **before** the standard password module:

**`/etc/pam.d/sudo`:**
```
# 1. Try face unlock first (sufficient = skip rest if successful)
auth  sufficient  pam_python.so /usr/local/lib/face-unlock/pam_face_unlock.py

# 2. Fallback: standard Unix password
@include common-auth
```

**`/etc/pam.d/common-auth`:**
```
# 1. Try face unlock first
auth  [success=done ignore=ignore default=1]  pam_python.so /usr/local/lib/face-unlock/pam_face_unlock.py

# 2. Standard Unix password (fallback)
auth  [success=1 default=ignore]  pam_unix.so nullok_secure try_first_pass

# 3. Deny if nothing matched
auth  requisite  pam_deny.so

# 4. Permit fallthrough
auth  required   pam_permit.so
```

#### PAM Module Logic

```python
def pam_sm_authenticate(pamh, flags, argv):
    # 1. Get username from PAM handle
    # 2. Check if face data exists at /etc/face-unlock/encodings/<user>.pkl
    #    → If not enrolled, return PAM_IGNORE (skip to next module)
    # 3. Launch animated UI (face-unlock-ui --mode scanning --timeout N)
    # 4. Run face engine subprocess
    # 5. If match → PAM_SUCCESS (grant access, show success UI)
    # 6. If no match → PAM_AUTH_ERR (fall through to password prompt)
```

#### Return Codes

| Code | Value | Meaning |
|------|-------|---------|
| `PAM_SUCCESS` | 0 | Face matched — access granted |
| `PAM_AUTH_ERR` | 7 | Not matched — falls through to password |
| `PAM_IGNORE` | 25 | No face enrolled — skip this module entirely |

---

### 3. Animated GTK4 UI

**File:** `src/ui/face_unlock_ui.py` (655 lines)

The crown jewel of the project — an iPhone Face ID–inspired GTK4 overlay with smooth Cairo animations.

#### UI States

| State | Visual | Description |
|-------|--------|-------------|
| `scanning` | 🟡 Golden rotating arc with glow pulse | Actively scanning for face |
| `success` | 🟢 Green ring fill animation + ✓ checkmark | Face matched! |
| `failed` | 🔴 Red ring + ✗ mark with horizontal shake | Face not recognized |
| `warning` | 🟠 Pulsing orange ring | Face Guardian countdown |
| `idle` | ⚪ Dim white ring | Waiting / password mode |

#### Face Ring Widget (Custom Cairo Drawing)

The `FaceRingWidget` class extends `Gtk.DrawingArea` and redraws at **60fps** using `GLib.timeout_add(16, ...)`:

- **Scanning ring:** A 280° arc that rotates 3.5° per frame, with a trailing fade and glowing outer ring that pulses via `sin()` easing
- **Success ring:** A green circle that fills from top (–90°) progress animates from 0→1 at +0.04/frame; a checkmark fades in at 90% complete
- **Failed ring:** Red full ring with X mark; horizontal shake offset decays as `8 × sin(t × 0.6) × max(0, 1 – t/40)`
- **Warning ring:** Full orange ring with sinusoidal pulsing glow (amplitude period ~63 frames)
- **Person silhouette:** A head (circle at y–22, r=28) and shoulders (half-circle at y+40, r=44) drawn with 30% white

#### CSS Theme

The UI uses a custom CSS stylesheet for the overlay:
- **Background:** `rgba(0, 0, 0, 0.88)` with 28px border radius
- **Typography:** SF Pro Display / Ubuntu / Inter font stack
- **Password field:** Glassmorphic entry with `rgba(255,255,255,0.12)` background
- **Color palette:** Success `#34C759`, Failure `#FF3B30`, Warning `#FF9500`

#### Window Features

- Transparent background with dark rounded overlay
- Center-aligned on screen
- Non-resizable (380×520)
- Keeps above other windows (GTK3)
- Password fallback with text entry and "Unlock" button
- Visual countdown during scanning
- Auto-close after 1.5s on success
- Demo mode cycles through all states at 2.5s intervals

#### GTK4 / GTK3 Fallback

The UI tries to import GTK4 + libadwaita first. If unavailable, it falls back to GTK3 with equivalent functionality. This ensures compatibility across Ubuntu 20.04 (GTK3) and 22.04+ (GTK4).

---

### 4. Face Guardian Daemon

**File:** `src/guardian/face_guardian.py` (241 lines)

An always-on background service that **continuously monitors the webcam** and **locks the screen** if the authorized user's face disappears for a configurable duration.

#### Behavior

1. **Polls every 2 seconds** — opens camera briefly, reads 3 frames (for auto-exposure), then releases
2. **Multi-model face detection:**
   - Primary: `face_recognition` HOG detector + dlib encoding comparison
   - Fallback: OpenCV Haar Cascades (frontal, profile, and flipped profile) to catch partial face views
3. **Countdown:** On face absence, launches the warning UI with a countdown timer
4. **Screen lock:** After `guard_lock_delay` seconds, locks the screen via:
   - `loginctl lock-session <id>` (primary)
   - `gdbus call -e -d org.gnome.ScreenSaver -m org.gnome.ScreenSaver.Lock` (fallback)
5. **Auto-pause:** Pauses when screen is already locked or when `guard_enabled = false`
6. **Safety:** Defaults to "authorized" if camera is busy, if dependencies are missing, or if frames fail to read — prevents accidental lockouts

#### Supporting Files

- **`face-guardian.service`** — systemd user service that runs the daemon after the graphical session starts, with auto-restart on failure
- **`toggle-guard.sh`** — Polkit-protected shell script that enables/disables the guard by editing `config.conf` and starting/stopping the systemd service for all active users

---

### 5. GNOME Shell Extension

**File:** `src/gnome-extension/extension.js` (83 lines)

A GNOME Shell extension (`face-unlock@face-unlock.ubuntu`) that adds a **Quick Toggle** tile to the system Quick Settings panel (the power/Wi-Fi/Bluetooth menu).

- **Toggle tile:** "Face Guard" with a lock icon (`changes-prevent-symbolic`)
- **Click action:** Runs `pkexec toggle-guard.sh enable/disable` for secure privilege escalation
- **State sync:** Polls `/etc/face-unlock/config.conf` every 2 seconds to keep the toggle in sync with external changes
- **Compatibility:** GNOME Shell versions 42, 43, 44, 45, 46, 47

---

### 6. Settings App (Lock Face)

**File:** `src/ui/settings_app.py` (391 lines)

The standalone libadwaita settings application branded as **"Lock Face"**. Provides:

- Hero section with enrollment status icon and label
- Face data management (enroll / delete with confirmation dialog)
- Face Guardian toggle with lock delay
- Match strictness slider with tick marks (Strict / Balanced / Relaxed)
- Scan timeout spinner
- "Apply Settings" button with toast notifications
- Direct systemd service management (start/stop `face-guardian.service`)

This app is registered via `face-unlock.desktop` and appears in the Ubuntu app menu.

---

### 7. Plymouth Boot Theme

**Files:** `src/boot/plymouth-theme/`

A custom Plymouth splash screen that shows during system boot:

| Component | Details |
|-----------|---------|
| **Background** | Dark charcoal (`rgb(13, 13, 18)`) |
| **Face outline** | White ellipse (120×150) with eye dots — person silhouette |
| **Scanning ring** | Golden 260° arc rotating at 4°/tick with pulsing glow — identical style to the GTK4 UI |
| **Success state** | Full green ring with "Unlocked" + "Welcome!" text |
| **Password state** | Red ring + password input box when face unlock is unavailable |
| **Typography** | Ubuntu Bold 16px (status), Ubuntu 12px (subtitle) |

The theme uses Plymouth's scripting API (`Window.GetEllipse`, `Window.GetQuadrangle`, etc.) to render the animation procedurally without any image assets.

---

### 8. UI Launcher Script

**File:** `src/ui/face-unlock-ui` (128 lines)

A critical Bash wrapper that ensures the GTK4 UI can launch correctly **regardless of how it's invoked** — whether from a `sudo` session, from PAM, from `su -`, or from a systemd service.

#### Display Environment Resolution

The script goes through multiple strategies to find the active graphical session:

1. **`loginctl list-sessions`** — finds sessions of type `x11` or `wayland`
2. **`systemctl --user show-environment`** — pulls `DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY` from the user's systemd environment
3. **`xdpyinfo` probing** — tests common display values (`:0`, `:1`, `:2`)
4. **`XAUTHORITY` search** — checks `~/.Xauthority`, `/run/user/<uid>/gdm/Xauthority`, `.mutter-Xwaylandauth*`
5. **`xhost` grants** — grants X access to root and the target user
6. **`SUDO_USER` fallback** — inherits display environment from the invoking sudo user

---

## ⚙️ Configuration

All settings are stored in a single INI-like file:

**`/etc/face-unlock/config.conf`**

```ini
# Face Unlock Configuration
# Edit values here or use GNOME Settings › Face Unlock

enabled_sudo        = true      # Use face auth for sudo commands
enabled_login       = true      # Use face auth for login / lock screen
threshold           = 0.55      # Match tolerance (0.3=strict → 0.75=relaxed)
require_attention   = false     # Require eyes open + looking at camera
timeout             = 8         # Seconds before falling back to password
guard_enabled       = false     # Enable always-on Face Guardian daemon
guard_lock_delay    = 30        # Seconds to wait before locking when face disappears
```

### Threshold Tuning Guide

| Value | Security Level | Notes |
|-------|---------------|-------|
| `0.30` | Very strict | May reject authentic faces in poor lighting |
| `0.40` | Strict | Good for high-security environments |
| `0.55` | **Balanced (default)** | Recommended for most users |
| `0.65` | Relaxed | Better in low light, slightly less secure |
| `0.75` | Very relaxed | May accept similar-looking faces |

---

## 🔄 Authentication Flow

### sudo / Login / Lock Screen

```
User triggers sudo / login
        │
        ▼
    PAM Stack
   (/etc/pam.d/sudo or common-auth)
        │
        ▼
┌─────────────────────────────┐
│  pam_python.so              │
│  → pam_face_unlock.py       │
│                             │
│  1. Check for enrolled face │
│     └─ No? → PAM_IGNORE    │──── Skip to password
│                             │
│  2. Launch UI (scanning)    │
│  3. Run face_engine.py      │
│                             │
│  4. Match? → PAM_SUCCESS    │──── ✅ Access Granted
│     └─ Show success UI      │
│                             │
│  5. No match / Timeout      │
│     → PAM_AUTH_ERR          │──── ❌ Falls through
│     └─ Show failed UI       │
└─────────────────────────────┘
        │
        ▼
  pam_unix.so → 🔑 Password Prompt
```

### Face Guardian

```
face-guardian.service running
        │
        ▼
    Poll every 2 seconds
        │
    ┌───▼───────────────┐
    │ Open camera       │
    │ Read 3 frames     │
    │ Release camera    │
    └───┬───────────────┘
        │
    ┌───▼───────────────────────────┐
    │ face_recognition HOG detect   │
    │ Compare with enrolled face    │
    │                               │
    │ Fallback: OpenCV Haar cascade │
    │ (frontal + profile + flipped) │
    └───┬───────────────────────────┘
        │
    ┌───▼───────────┐        ┌──────────────────┐
    │ Face present? │── Yes ─▶│ Reset timer      │
    │               │        │ Dismiss warning   │
    └───┬───────────┘        └──────────────────┘
        │ No
        ▼
    Start countdown
    Show warning UI (orange pulse)
        │
    countdown > guard_lock_delay?
        │ Yes
        ▼
    🔒 Lock Screen
    (loginctl + gdbus fallback)
```

---

## 📂 Installed Files & Paths

| Path | Purpose |
|------|---------|
| `/usr/local/lib/face-unlock/` | Core library files (engine, UI, guardian, scripts) |
| `/usr/local/bin/face-unlock-ui` | UI launcher script (display env resolver) |
| `/etc/face-unlock/config.conf` | Configuration file |
| `/etc/face-unlock/encodings/<user>.pkl` | User's face encoding data (chmod 600) |
| `/etc/face-unlock/backups/` | Backed-up original PAM configs |
| `/lib/security/pam_face_unlock.py` | PAM module loaded by pam_python.so |
| `/etc/pam.d/sudo` | Modified PAM config for sudo |
| `/etc/pam.d/common-auth` | Modified PAM config for login/lock screen |
| `/usr/share/plymouth/themes/face-unlock/` | Plymouth boot theme files |

| `/usr/share/gnome-shell/extensions/face-unlock@face-unlock.ubuntu/` | GNOME Shell extension files |
| `/etc/systemd/user/face-guardian.service` | Face Guardian systemd user service |
| `/usr/share/polkit-1/actions/com.face-unlock.policy` | Polkit policy for enrollment and guard |
| `/var/log/face-unlock.log` | Authentication log file |

---

## 🔒 Security Model

| Aspect | Implementation |
|--------|----------------|
| **Local-only** | All face data stored on-device. No cloud, no network, no telemetry. |
| **Encrypted storage** | Face encodings stored as Python pickle (`.pkl`) with `chmod 600` (owner-read only) |
| **PAM `sufficient`** | Password always works as fallback — face unlock is additive, never exclusive |
| **PAM backup** | Original `/etc/pam.d/sudo` and `/etc/pam.d/common-auth` are backed up before modification |
| **Privilege escalation** | Enrollment and guard toggling use PolicyKit (`pkexec`) — users are prompted for password |
| **Anti-lockout** | If face_recognition fails, PAM returns `AUTH_ERR` and falls through to password. Guardian defaults to "authorized" on errors. |
| **Multi-model enrollment** | 15 samples with `num_jitters=100` and `model="large"` create robust encodings from multiple angles |
| **On-device inference** | dlib CNN runs entirely on CPU — no GPU or internet required |
| **Confidence logging** | All authentication attempts logged to `/var/log/face-unlock.log` with timestamps |
| **Anti-spoofing** | Multi-angle enrollment + high jitter count makes photo-based attacks harder (though not impossible without dedicated liveness detection) |

### Recovery from Lockout

If face unlock causes authentication issues:

```bash
# Boot into recovery mode (hold Shift during boot → select "root shell")
# Then restore original PAM:
sudo bash /path/to/uninstall.sh

# Or manually:
cp /etc/face-unlock/backups/sudo.bak /etc/pam.d/sudo
cp /etc/face-unlock/backups/common-auth.bak /etc/pam.d/common-auth
```

---

## 🗑️ Uninstallation

```bash
sudo bash uninstall.sh
```

The uninstaller:
1. **Restores original PAM configs** from `/etc/face-unlock/backups/`
2. **Removes all installed files** — library, configs, encodings, PAM module, Plymouth theme, GNOME panel, Polkit policy, extension, logs
3. **Resets Plymouth theme** to system default

---

## 🐛 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Camera not detected | Wrong camera index | Set `FACE_UNLOCK_CAMERA=1` (or 2, etc.) |
| False rejections | Threshold too strict | Increase threshold in config (e.g., `0.65`) |
| False accepts | Threshold too relaxed | Decrease threshold (e.g., `0.40`) |
| Face unlock too slow | Lighting or camera quality | Improve lighting; reduce timeout |
| UI doesn't appear | Display env variables lost | Fixed by the `face-unlock-ui` launcher script; check `DISPLAY` and `XAUTHORITY` |
| sudo locked out | PAM misconfiguration | Boot recovery → `sudo bash uninstall.sh` |
| Plymouth not showing | initramfs not updated | `sudo update-initramfs -u` |
| Guardian not locking | Service not running | `systemctl --user status face-guardian.service` |
| pkexec hangs | Polkit agent not running | Ensure GNOME session is active; restart polkit |
| dlib compilation fails | Missing build deps | `sudo apt install cmake build-essential libatlas-base-dev` |

### Useful Commands

```bash
# Check auth logs
sudo tail -f /var/log/face-unlock.log

# Check Guardian service status
systemctl --user status face-guardian.service

# View Guardian service logs
journalctl --user -u face-guardian.service -f

# Test face engine directly
python3 /usr/local/lib/face-unlock/face_engine.py --user $USER --verbose

# Run UI in demo mode
python3 /usr/local/lib/face-unlock/face_unlock_ui.py --demo

# Manually toggle Face Guard
sudo /usr/local/lib/face-unlock/toggle-guard.sh enable   # or 'disable'
```

---

## 🛠 Tech Stack

| Technology | Role |
|------------|------|
| **Python 3** | Primary language for all modules |
| **OpenCV** | Camera I/O, frame processing, Haar cascade face detection |
| **dlib** | Deep CNN face embedding model (128-dimensional vectors) |
| **face_recognition** | High-level wrapper around dlib for face detection and comparison |
| **GTK4 + libadwaita** | Modern GNOME-native UI components (Lock Face settings app) |
| **GTK DrawingArea + Cairo** | Custom-drawn animated Face ID ring widget |
| **PAM (pam_python)** | Pluggable Authentication Module integration |
| **Plymouth** | Boot splash screen animation (Face ID theme) |
| **systemd** | User service management for Face Guardian daemon |
| **PolicyKit (polkit)** | Secure privilege escalation for enrollment and guard management |
| **GNOME Shell (GJS)** | Quick Settings toggle extension |
| **Bash** | Installer, uninstaller, enrollment wrapper, UI launcher, guard toggle |
| **NumPy** | Array operations for face encoding vectors |
| **Pickle** | Serialization of face encoding data |

---

## 📄 License

This project is developed for personal use on Ubuntu systems. See the project repository for license details.

---

<p align="center">
  <em>Built with ❤️ for Ubuntu by Sarvesh Jadiya</em>
</p>
