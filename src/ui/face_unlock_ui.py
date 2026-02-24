#!/usr/bin/env python3
"""
Face Unlock — iPhone-like GTK4 UI
Animated face unlock overlay with Face ID style scanning ring.

Usage:
  python3 face_unlock_ui.py --mode scanning
  python3 face_unlock_ui.py --mode success
  python3 face_unlock_ui.py --mode failed
  python3 face_unlock_ui.py --demo     (cycles through all states)
"""

import sys
import os
import time
import math
import argparse
import threading
import logging

# Setup Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("face_unlock_ui")
logger.info("Starting Face Unlock UI...")
logger.debug(f"Environment: DISPLAY={os.environ.get('DISPLAY')}, XAUTHORITY={os.environ.get('XAUTHORITY')}, XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR')}")

try:
    logger.debug("Attempting to import GTK4/Adwaita...")
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, GLib, Gdk, Pango, Gio
    HAS_GTK4 = True
    logger.info("Using GTK4 and Adwaita.")
except ImportError as e:
    logger.warning(f"GTK4 import failed: {e}")
    HAS_GTK4 = False
    try:
        logger.debug("Attempting to import GTK3...")
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib, Gdk, Pango
        HAS_GTK3 = True
        logger.info("Using GTK3.")
    except ImportError as e2:
        logger.error(f"GTK3 import failed: {e2}")
        HAS_GTK3 = False

# ─── CSS Stylesheet ────────────────────────────────────────────────────────────

GTK_CSS = b"""
/* ===== Root / Window ===== */
window {
    background-color: transparent;
}

/* ===== Main overlay ===== */
.unlock-overlay {
    background: rgba(0, 0, 0, 0.88);
    border-radius: 28px;
}

/* ===== Face ring container ===== */
.face-ring-container {
    margin: 40px;
}

/* ===== Status label ===== */
.status-label {
    font-family: 'SF Pro Display', 'Ubuntu', 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.85);
    margin-top: 16px;
    letter-spacing: 0.3px;
}

.status-label.success {
    color: #34C759;
}

.status-label.failed {
    color: #FF3B30;
}

.status-label.warning {
    color: #FF9500;
}

.status-label.scanning {
    color: #FFFFFF;
}

/* ===== Subtitle ===== */
.subtitle-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.45);
    margin-top: 6px;
}

/* ===== Password fallback field ===== */
.password-entry {
    background: rgba(255, 255, 255, 0.12);
    border: 1.5px solid rgba(255, 255, 255, 0.2);
    border-radius: 14px;
    color: white;
    font-size: 16px;
    padding: 14px 20px;
    margin-top: 24px;
    min-width: 260px;
}

.password-entry:focus {
    border-color: rgba(255, 255, 255, 0.5);
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.08);
    outline: none;
}

/* ===== Fallback button ===== */
.fallback-button {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.45);
    font-size: 13px;
    margin-top: 12px;
    padding: 8px 16px;
    border-radius: 10px;
}

.fallback-button:hover {
    color: rgba(255, 255, 255, 0.75);
    background: rgba(255, 255, 255, 0.08);
}

/* ===== Enter password button ===== */
.enter-button {
    background: rgba(255, 255, 255, 0.15);
    border: none;
    border-radius: 14px;
    color: white;
    font-size: 15px;
    font-weight: 600;
    padding: 12px 32px;
    margin-top: 12px;
    transition: background 200ms;
}

.enter-button:hover {
    background: rgba(255, 255, 255, 0.22);
}

/* ===== Lock icon ===== */
.lock-icon {
    font-size: 36px;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 8px;
}
"""

# ─── Drawing Area (Custom Face Ring) ──────────────────────────────────────────

class FaceRingWidget(Gtk.DrawingArea):
    """
    Custom drawn Face ID–like scanning ring.
    States: scanning, success, failed, warning, idle
    """

    RING_SIZE = 200
    RING_THICKNESS = 6

    def __init__(self):
        super().__init__()
        self.set_size_request(self.RING_SIZE, self.RING_SIZE)
        self.state = "scanning"
        self.angle = 0.0          # rotation angle for scanning arc
        self.pulse = 0.0          # pulsing glow amount
        self.fill_progress = 0.0  # fill level on success
        self.shake_offset = 0.0   # x offset on failure
        self._tick = 0

        if HAS_GTK4:
            self.set_draw_func(self._draw_gtk4)
        else:
            self.connect("draw", self._draw_gtk3)

        # Animation timer — 60fps
        GLib.timeout_add(16, self._animate)

    def set_state(self, state: str):
        self.state = state
        if state == "success":
            self.fill_progress = 0.0
        elif state == "failed":
            self.shake_offset = 0.0

    def _animate(self):
        self._tick += 1
        if self.state == "scanning":
            self.angle = (self.angle + 3.5) % 360
            self.pulse = 0.5 + 0.5 * math.sin(self._tick * 0.08)
        elif self.state == "success":
            self.fill_progress = min(1.0, self.fill_progress + 0.04)
        elif self.state == "failed":
            t = self._tick % 40
            self.shake_offset = 8 * math.sin(t * 0.6) * max(0, 1 - t / 40)
        elif self.state == "warning":
            self.pulse = 0.5 + 0.5 * math.sin(self._tick * 0.1)

        self.queue_draw()
        return True  # keep timer running

    def _draw_gtk4(self, widget, cr, width, height):
        self._paint(cr, width, height)

    def _draw_gtk3(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        self._paint(cr, w, h)

    def _paint(self, cr, width, height):
        cx = width / 2 + self.shake_offset
        cy = height / 2
        r = (min(width, height) / 2) - 14

        # ── Background circle ──────────────────────────────────────────────
        cr.set_source_rgba(1, 1, 1, 0.06)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()

        # ── Face icon (person silhouette) ──────────────────────────────────
        # Head
        cr.set_source_rgba(1, 1, 1, 0.3)
        cr.arc(cx, cy - 22, 28, 0, 2 * math.pi)
        cr.fill()
        # Shoulders
        cr.arc(cx, cy + 40, 44, math.pi, 2 * math.pi)
        cr.fill()

        # ── State rendering ────────────────────────────────────────────────
        if self.state == "scanning":
            self._draw_scanning_ring(cr, cx, cy, r)
        elif self.state == "success":
            self._draw_success_ring(cr, cx, cy, r)
        elif self.state == "failed":
            self._draw_failed_ring(cr, cx, cy, r)
        elif self.state == "warning":
            self._draw_warning_ring(cr, cx, cy, r)
        elif self.state == "idle":
            self._draw_idle_ring(cr, cx, cy, r)

    def _draw_scanning_ring(self, cr, cx, cy, r):
        import math

        start = math.radians(self.angle - 30)
        end   = math.radians(self.angle + 250)

        # Glow effect
        glow_alpha = 0.12 + 0.08 * self.pulse
        cr.set_source_rgba(1.0, 0.85, 0.0, glow_alpha)
        cr.set_line_width(self.RING_THICKNESS * 3.5)
        cr.arc(cx, cy, r, start, end)
        cr.stroke()

        # Main arc — golden yellow (Face ID color)
        cr.set_source_rgba(1.0, 0.85, 0.0, 0.95)
        cr.set_line_width(self.RING_THICKNESS)
        cr.arc(cx, cy, r, start, end)
        cr.stroke()

        # Trailing fade — light arc behind
        cr.set_source_rgba(1.0, 0.85, 0.0, 0.25)
        cr.set_line_width(self.RING_THICKNESS * 0.5)
        cr.arc(cx, cy, r, end, end + math.radians(60))
        cr.stroke()

    def _draw_success_ring(self, cr, cx, cy, r):
        end_angle = 2 * math.pi * self.fill_progress

        # Background ring
        cr.set_source_rgba(0.2, 0.78, 0.35, 0.15)
        cr.set_line_width(self.RING_THICKNESS)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

        # Green fill ring
        cr.set_source_rgba(0.2, 0.78, 0.35, 1.0)
        cr.set_line_width(self.RING_THICKNESS)
        cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + end_angle)
        cr.stroke()

        # Checkmark when complete
        if self.fill_progress > 0.9:
            cr.set_source_rgba(0.2, 0.78, 0.35, min(1.0, (self.fill_progress - 0.9) * 10))
            cr.set_line_width(5)
            cr.set_line_cap(1)  # round cap
            s = 20
            cr.move_to(cx - s * 0.5, cy)
            cr.line_to(cx - s * 0.1, cy + s * 0.4)
            cr.line_to(cx + s * 0.6, cy - s * 0.4)
            cr.stroke()

    def _draw_failed_ring(self, cr, cx, cy, r):
        # Red full ring
        cr.set_source_rgba(1.0, 0.23, 0.19, 0.2)
        cr.set_line_width(self.RING_THICKNESS * 2)
        cr.arc(cx + self.shake_offset, cy, r, 0, 2 * math.pi)
        cr.stroke()

        cr.set_source_rgba(1.0, 0.23, 0.19, 0.9)
        cr.set_line_width(self.RING_THICKNESS)
        cr.arc(cx + self.shake_offset, cy, r, 0, 2 * math.pi)
        cr.stroke()

        # X mark
        cr.set_source_rgba(1.0, 0.23, 0.19, 0.8)
        cr.set_line_width(5)
        cr.set_line_cap(1)
        s = 18
        cx2 = cx + self.shake_offset
        cr.move_to(cx2 - s, cy - s); cr.line_to(cx2 + s, cy + s); cr.stroke()
        cr.move_to(cx2 + s, cy - s); cr.line_to(cx2 - s, cy + s); cr.stroke()

    def _draw_warning_ring(self, cr, cx, cy, r):
        # Pulsing orange glow
        glow_alpha = 0.2 + 0.15 * self.pulse
        cr.set_source_rgba(1.0, 0.58, 0.0, glow_alpha)
        cr.set_line_width(self.RING_THICKNESS * 4)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

        # Solid orange ring
        cr.set_source_rgba(1.0, 0.58, 0.0, 0.95)
        cr.set_line_width(self.RING_THICKNESS)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

    def _draw_idle_ring(self, cr, cx, cy, r):
        cr.set_source_rgba(1, 1, 1, 0.2)
        cr.set_line_width(self.RING_THICKNESS)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

# ─── Main Window ───────────────────────────────────────────────────────────────

class FaceUnlockWindow:
    def __init__(self, initial_mode="scanning", on_password=None, timeout=0):
        self.mode = initial_mode
        self.on_password = on_password
        self.password_shown = False
        self.timeout_remaining = timeout

        if HAS_GTK4:
            self.app = Adw.Application(
                application_id=None,
                flags=Gio.ApplicationFlags.NON_UNIQUE
            )
            self.app.connect("activate", self._build_ui)
        else:
            self._build_ui_gtk3()

    def _apply_css(self):
        provider = Gtk.CssProvider()
        if HAS_GTK4:
            provider.load_from_data(GTK_CSS)
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            else:
                print("Warning: Gdk.Display.get_default() returned None")
        else:
            try:
                provider.load_from_data(GTK_CSS)
                Gtk.StyleContext.add_provider_for_screen(
                    Gdk.Screen.get_default(),
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            except Exception as e:
                logger.error(f"CSS loading error: {e}")

    def _build_ui(self, app=None):
        logger.debug(f"Entered _build_ui, app={app}")
        self._apply_css()

        if HAS_GTK4:
            self.win = Gtk.ApplicationWindow(application=app)
        else:
            self.win = Gtk.Window()
            self.win.connect("destroy", Gtk.main_quit)

        self.win.set_title("Face Unlock")
        logger.debug(f"Building UI: mode={self.mode}, timeout={self.timeout_remaining}")
        self.win.set_default_size(380, 520)
        self.win.set_resizable(False)

        # Make it float above everything
        if not HAS_GTK4:
            self.win.set_keep_above(True)
            self.win.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        # Center on screen
        self.win.set_halign(Gtk.Align.CENTER)
        self.win.set_valign(Gtk.Align.CENTER)

        # ── Layout ────────────────────────────────────────────────────────
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        if HAS_GTK4:
            outer.add_css_class("unlock-overlay")
        else:
            outer.get_style_context().add_class("unlock-overlay")

        # Spacer top
        if HAS_GTK4:
            outer.append(Gtk.Box())
        else:
            outer.pack_start(Gtk.Box(), True, True, 20)

        # Lock icon
        icon_label = Gtk.Label(label="")
        if HAS_GTK4:
            icon_label.add_css_class("lock-icon")
        else:
            icon_label.get_style_context().add_class("lock-icon")
        self._add_widget(outer, icon_label, 0, 32, 0, 8)

        # Face ring
        self.ring = FaceRingWidget()
        self._add_widget(outer, self.ring, 0, 8, 0, 8)

        # Status label
        self.status_label = Gtk.Label(label=self._get_status_text())
        if HAS_GTK4:
            self.status_label.add_css_class("status-label")
            self.status_label.add_css_class(self.mode)
        else:
            self.status_label.get_style_context().add_class("status-label")
        self._add_widget(outer, self.status_label, 0, 4, 0, 0)

        # Subtitle
        self.subtitle_label = Gtk.Label(label=self._get_subtitle_text())
        if HAS_GTK4:
            self.subtitle_label.add_css_class("subtitle-label")
        else:
            self.subtitle_label.get_style_context().add_class("subtitle-label")
        self._add_widget(outer, self.subtitle_label, 0, 28, 0, 0)

        # Password fallback section
        self.pass_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pass_box.set_halign(Gtk.Align.CENTER)

        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Enter password…")
        if HAS_GTK4:
            self.entry.add_css_class("password-entry")
        else:
            self.entry.get_style_context().add_class("password-entry")
        self.entry.connect("activate", self._on_password_enter)

        self.enter_btn = Gtk.Button(label="Unlock")
        if HAS_GTK4:
            self.enter_btn.add_css_class("enter-button")
        else:
            self.enter_btn.get_style_context().add_class("enter-button")
        self.enter_btn.connect("clicked", self._on_password_enter)

        self._add_widget(self.pass_box, self.entry, 0, 8, 0, 0)
        self._add_widget(self.pass_box, self.enter_btn, 0, 0, 0, 0)
        self._add_widget(outer, self.pass_box, 0, 0, 32, 0)

        # Fallback button (shown during scanning)
        self.fallback_btn = Gtk.Button(label="Use Password Instead")
        if HAS_GTK4:
            self.fallback_btn.add_css_class("fallback-button")
        else:
            self.fallback_btn.get_style_context().add_class("fallback-button")
        self.fallback_btn.connect("clicked", self._show_password_fallback)
        self._add_widget(outer, self.fallback_btn, 0, 0, 0, 24)

        # Initially hide password box, show fallback button only when scanning
        self.pass_box.set_visible(False)

        self._add_widget_fill(outer, Gtk.Box(), 20)

        if HAS_GTK4:
            self.win.set_child(outer)
            self.win.present()
            self.set_mode(self.mode)
        else:
            self.win.add(outer)

    def _build_ui_gtk3(self):
        self._build_ui()
        # BUG FIX: Removed Gtk.main() here to prevent double loop.

    def _add_widget(self, parent, widget, top, bottom, start, end):
        widget.set_margin_top(top)
        widget.set_margin_bottom(bottom)
        widget.set_margin_start(start)
        widget.set_margin_end(end)
        widget.set_halign(Gtk.Align.CENTER)
        if HAS_GTK4:
            parent.append(widget)
        else:
            parent.pack_start(widget, False, False, 0)

    def _add_widget_fill(self, parent, widget, margin):
        widget.set_margin_top(margin)
        if HAS_GTK4:
            parent.append(widget)
        else:
            parent.pack_start(widget, True, True, margin)

    def _get_status_text(self):
        return {
            "scanning": "Face ID",
            "success":  "Unlocked",
            "failed":   "Not Recognized",
            "warning":  "Warning",
            "idle":     "Face Unlock",
        }.get(self.mode, "Face Unlock")

    def _get_subtitle_text(self):
        if self.mode == "scanning":
            if getattr(self, "timeout_remaining", 0) > 0:
                return f"Move your face into view ({self.timeout_remaining}s remaining)"
            return "Move your face into view"
        if self.mode == "warning":
            if getattr(self, "timeout_remaining", 0) > 0:
                return f"Authorized face not detected ({self.timeout_remaining}s)\nLocking screen"
            return "Authorized face not detected"
        return {
            "success":  "Welcome back!",
            "failed":   "Face not recognized — use password",
            "idle":     "",
        }.get(self.mode, "")

    def set_mode(self, mode: str):
        self.mode = mode
        self.ring.set_state(mode)
        self.status_label.set_text(self._get_status_text())
        self.subtitle_label.set_text(self._get_subtitle_text())

        if mode == "failed":
            # Show password fallback after failure
            GLib.timeout_add(1200, self._show_password_fallback)
        elif mode == "success":
            # Auto-close after success animation
            GLib.timeout_add(1500, self._close)
        elif mode in ["scanning", "warning"] and getattr(self, "timeout_remaining", 0) > 0:
            GLib.timeout_add_seconds(1, self._countdown_tick)

        self.fallback_btn.set_visible(mode == "scanning")

    def _countdown_tick(self, *_):
        if self.mode in ["scanning", "warning"]:
            self.timeout_remaining -= 1
            if self.timeout_remaining >= 0:
                self.subtitle_label.set_text(self._get_subtitle_text())
                return True
        return False

    def _show_password_fallback(self, *_):
        if not self.password_shown:
            self.password_shown = True
            self.pass_box.set_visible(True)
            self.fallback_btn.set_visible(False)
            self.ring.set_state("idle")
            self.status_label.set_text("Enter Password")
            self.subtitle_label.set_text("Face unlock unavailable")
            self.entry.grab_focus()
        return False

    def _on_password_enter(self, *_):
        password = self.entry.get_text()
        if self.on_password:
            self.on_password(password)
        self._close()

    def _close(self, *_):
        if HAS_GTK4:
            self.app.quit()
        else:
            Gtk.main_quit()
        return False

    def run(self):
        if HAS_GTK4:
            logger.debug("Starting Adw.Application.run()")
            # Pass only the script name to avoid GTK parsing our custom args
            self.app.run([sys.argv[0]])
            logger.debug("Adw.Application.run() has returned.")
        else:
            self.win.show_all()
            self.win.present()
            self.set_mode(self.mode)
            Gtk.main()

# ─── Demo Mode ────────────────────────────────────────────────────────────────

class DemoMode:
    """Cycle through all states for testing/preview."""
    def __init__(self, ui):
        self.ui = ui
        self.states = ["scanning", "success", "scanning", "failed", "scanning"]
        self.idx = 0
        GLib.timeout_add(2500, self._next_state)

    def _next_state(self):
        if self.idx < len(self.states):
            self.ui.set_mode(self.states[self.idx])
            self.idx += 1
            return True
        return False

# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Face Unlock UI")
    parser.add_argument("--mode", default="scanning",
                        choices=["scanning", "success", "failed", "warning", "idle"],
                        help="Initial display mode")
    parser.add_argument("--timeout", type=int, default=0,
                        help="Optional timeout in seconds for scanning countdown")
    parser.add_argument("--demo", action="store_true",
                        help="Demo mode: cycle through all states")
    args = parser.parse_args()

    if not HAS_GTK4 and not HAS_GTK3:
        logger.error("❌ GTK4 or GTK3 with GObject introspection not found.")
        sys.exit(1)

    logger.debug(f"Creating FaceUnlockWindow with mode={args.mode}")
    app = FaceUnlockWindow(initial_mode=args.mode, timeout=args.timeout)

    if args.demo:
        logger.info("Demo mode enabled.")
        DemoMode(app)

    logger.info("Running GTK main loop...")
    app.run()

if __name__ == "__main__":
    main()
