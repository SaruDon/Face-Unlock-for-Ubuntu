#!/usr/bin/env python3
import sys
import os
import subprocess
import getpass
import threading
import logging
from pathlib import Path

# Configure logging to stdout and a file for easy monitoring
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/face-unlock-settings.log")
    ]
)
log = logging.getLogger("settings_app")

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, GLib, Gio
except ImportError as e:
    print(f"Failed to import GTK4/Adwaita: {e}")
    sys.exit(1)

class FaceUnlockSettings(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.github.jadiya.FaceUnlock',
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        
        self.username = os.environ.get("SUDO_USER", os.environ.get("USER", getpass.getuser()))
        self.encoding_path = Path(f"/etc/face-unlock/encodings/{self.username}.pkl")
        self.config_path = Path("/etc/face-unlock/config.conf")

    def read_config(self):
        """Parse config.conf into a dict."""
        defaults = {
            "guard_enabled": "false",
            "guard_lock_delay": "30",
            "threshold": "0.55",
            "timeout": "20",
        }
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            k, v = line.split("=", 1)
                            defaults[k.strip()] = v.strip()
            except Exception:
                pass
        return defaults

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self, title="Lock Face")
        self.win.set_default_size(500, 600)
        
        # Main layout container
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Header bar
        header = Adw.HeaderBar()
        self.box.append(header)
        
        # Content group
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_margin_top(32)
        content_box.set_margin_bottom(32)
        content_box.set_margin_start(32)
        content_box.set_margin_end(32)
        self.box.append(content_box)

        # Title/Status Hero Section
        self.status_icon = Gtk.Image()
        self.status_icon.set_pixel_size(96)
        self.status_icon.add_css_class("dim-label")
        content_box.append(self.status_icon)

        self.status_label = Gtk.Label()
        self.status_label.add_css_class("title-1")
        content_box.append(self.status_label)
        
        # Preferences Page
        page = Adw.PreferencesPage()
        content_box.append(page)
        
        # Enrollment Group
        self.enroll_group = Adw.PreferencesGroup(title="Face Data", description="Manage your enrolled face data.")
        page.add(self.enroll_group)
        
        # Action row for enrollment
        self.enroll_row = Adw.ActionRow(title="Enroll Face")
        self.enroll_row.set_subtitle("Scan your face to enable authentication")
        
        self.enroll_btn = Gtk.Button(label="Setup")
        self.enroll_btn.add_css_class("suggested-action")
        self.enroll_btn.set_valign(Gtk.Align.CENTER)
        self.enroll_btn.connect("clicked", self.on_enroll_clicked)
        self.enroll_row.add_suffix(self.enroll_btn)
        self.enroll_group.add(self.enroll_row)
        
        # Action row for deletion
        self.delete_row = Adw.ActionRow(title="Remove Face Data")
        self.delete_row.set_subtitle("Delete your face scans securely")
        
        self.delete_btn = Gtk.Button(label="Delete")
        self.delete_btn.add_css_class("destructive-action")
        self.delete_btn.set_valign(Gtk.Align.CENTER)
        self.delete_btn.connect("clicked", self.on_delete_clicked)
        self.delete_row.add_suffix(self.delete_btn)
        self.enroll_group.add(self.delete_row)

        # Guardian Group
        self.guard_group = Adw.PreferencesGroup(title="Face Guardian", description="Always-on background face monitoring.")
        page.add(self.guard_group)
        
        # Guardian Toggle
        self.guard_row = Adw.ActionRow(title="Lock when face disappears")
        self.guard_row.set_subtitle("Automatically locks screen when you walk away")
        
        self.guard_switch = Gtk.Switch()
        self.guard_switch.set_valign(Gtk.Align.CENTER)
        self.guard_row.add_suffix(self.guard_switch)
        self.guard_group.add(self.guard_row)
        
        # Guard Lock Delay
        guard_delay_row = Adw.ActionRow(title="Lock Delay (seconds)")
        guard_delay_row.set_subtitle("Wait time before locking after face disappears")
        
        self.guard_delay_spin = Gtk.SpinButton.new_with_range(5, 120, 5)
        self.guard_delay_spin.set_valign(Gtk.Align.CENTER)
        guard_delay_row.add_suffix(self.guard_delay_spin)
        self.guard_group.add(guard_delay_row)
        
        # Security Group
        self.security_group = Adw.PreferencesGroup(
            title="Security",
            description="Lower sensitivity = stricter matching (more secure, may need better lighting)"
        )
        page.add(self.security_group)
        
        # Match Strictness Slider
        sens_row = Adw.ActionRow(title="Match Strictness")
        
        slider_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        slider_box.set_valign(Gtk.Align.CENTER)
        
        lbl_strict = Gtk.Label(label="Strict")
        lbl_strict.add_css_class("dim-label")
        
        self.strictness_slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.3, 0.75, 0.05
        )
        self.strictness_slider.set_size_request(200, -1)
        self.strictness_slider.set_draw_value(False)
        for v in [0.3, 0.55, 0.75]:
            self.strictness_slider.add_mark(v, Gtk.PositionType.BOTTOM, None)
        
        lbl_relaxed = Gtk.Label(label="Relaxed")
        lbl_relaxed.add_css_class("dim-label")
        
        slider_box.append(lbl_strict)
        slider_box.append(self.strictness_slider)
        slider_box.append(lbl_relaxed)
        
        sens_row.add_suffix(slider_box)
        self.security_group.add(sens_row)
        
        # Scan Timeout
        timeout_row = Adw.ActionRow(title="Scan Timeout")
        timeout_row.set_subtitle("Seconds to wait before falling back to password")
        
        self.timeout_spin = Gtk.SpinButton.new_with_range(3, 60, 1)
        self.timeout_spin.set_valign(Gtk.Align.CENTER)
        timeout_row.add_suffix(self.timeout_spin)
        self.security_group.add(timeout_row)
        
        # Apply Settings Group
        self.apply_group = Adw.PreferencesGroup()
        page.add(self.apply_group)
        
        self.apply_btn = Gtk.Button(label="Apply Settings")
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.add_css_class("pill")
        self.apply_btn.set_margin_top(16)
        self.apply_btn.set_halign(Gtk.Align.CENTER)
        self.apply_btn.connect("clicked", self.on_apply_clicked)
        self.apply_group.add(self.apply_btn)

        # Wrap in ToastOverlay so we can show toasts
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.box)
        self.win.set_content(self.toast_overlay)
        self.refresh_state()
        self.win.present()
        
    def refresh_state(self):
        # Check if enrolled (may fail if encodings dir is root-only)
        try:
            is_enrolled = self.encoding_path.exists()
        except PermissionError:
            is_enrolled = False
        
        if is_enrolled:
            self.status_icon.set_from_icon_name("camera-web-symbolic")
            self.status_icon.remove_css_class("dim-label")
            self.status_icon.add_css_class("success")
            self.status_label.set_text("Face Enrolled")
            
            self.enroll_btn.set_sensitive(False)
            self.delete_btn.set_sensitive(True)
            self.guard_switch.set_sensitive(True)
        else:
            self.status_icon.set_from_icon_name("avatar-default-symbolic")
            self.status_icon.remove_css_class("success")
            self.status_icon.add_css_class("dim-label")
            self.status_label.set_text("Not Enrolled")
            
            self.enroll_btn.set_sensitive(True)
            self.delete_btn.set_sensitive(False)
            self.guard_switch.set_sensitive(False)
            
        # Load all config values
        cfg = self.read_config()
        self.guard_switch.set_active(cfg["guard_enabled"].lower() == "true")
        
        try:
            self.guard_delay_spin.set_value(float(cfg.get("guard_lock_delay", "30")))
        except (ValueError, TypeError):
            self.guard_delay_spin.set_value(30)
        
        try:
            self.strictness_slider.set_value(float(cfg.get("threshold", "0.55")))
        except (ValueError, TypeError):
            self.strictness_slider.set_value(0.55)
        
        try:
            self.timeout_spin.set_value(float(cfg.get("timeout", "20")))
        except (ValueError, TypeError):
            self.timeout_spin.set_value(20)

    def on_enroll_clicked(self, btn):
        log.info("Enroll Face button clicked.")
        self.enroll_btn.set_sensitive(False)
        def task():
            log.info("Starting enrollment process...")
            self.run_pkexec_command(["/usr/bin/python3", "/usr/local/lib/face-unlock/enroll.py"])
            log.info("Enrollment process finished. Refreshing state.")
            GLib.idle_add(self.refresh_state)
        threading.Thread(target=task, daemon=True).start()

    def on_delete_clicked(self, btn):
        dialog = Adw.MessageDialog(heading="Delete face data?",
                                   body="This cannot be undone. You will need to use your password to unlock the PC.",
                                   transient_for=self.win)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        
        def on_response(dlg, response):
            log.info(f"Delete face data dialog response: {response}")
            if response == "delete":
                self.delete_btn.set_sensitive(False)
                def task():
                    log.info("Starting face data deletion...")
                    self.run_pkexec_command(["/usr/bin/python3", "/usr/local/lib/face-unlock/enroll.py", "--delete"])
                    log.info("Deletion process finished. Refreshing state.")
                    GLib.idle_add(self.refresh_state)
                threading.Thread(target=task, daemon=True).start()
                
        dialog.connect("response", on_response)
        dialog.present()

    def on_apply_clicked(self, btn):
        log.info("================ START APPLY ===============")
        self.apply_btn.set_sensitive(False)
        
        # Gather all values from the UI
        guard_state = self.guard_switch.get_active()
        guard_value = "true" if guard_state else "false"
        lock_delay = str(int(self.guard_delay_spin.get_value()))
        threshold = str(round(self.strictness_slider.get_value(), 2))
        timeout = str(int(self.timeout_spin.get_value()))
        
        log.info(f"Applying: guard_enabled={guard_value}, guard_lock_delay={lock_delay}, "
                 f"threshold={threshold}, timeout={timeout}")
        
        def task():
            # 1. Read existing config, update all keys, write back
            try:
                updates = {
                    "guard_enabled": guard_value,
                    "guard_lock_delay": lock_delay,
                    "threshold": threshold,
                    "timeout": timeout,
                }
                
                lines = []
                if self.config_path.exists():
                    with open(self.config_path, "r") as f:
                        lines = f.readlines()
                
                keys_written = set()
                with open(self.config_path, "w") as f:
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith("#") or "=" not in stripped:
                            f.write(line)
                            continue
                        key = stripped.split("=", 1)[0].strip()
                        if key in updates:
                            f.write(f"{key} = {updates[key]}\n")
                            keys_written.add(key)
                        else:
                            f.write(line)
                    # Write any new keys that weren't in the file
                    for key, val in updates.items():
                        if key not in keys_written:
                            f.write(f"{key} = {val}\n")
                
                log.info("Config file updated successfully.")
            except Exception as e:
                log.error(f"Failed to update config: {e}")
                toast = Adw.Toast.new(f"❌ Error saving settings: {e}")
                toast.set_timeout(3)
                GLib.idle_add(self.toast_overlay.add_toast, toast)
                GLib.idle_add(self.apply_btn.set_sensitive, True)
                return
            
            # 2. Start or stop the guardian service
            try:
                if guard_state:
                    log.info("Restarting face-guardian.service...")
                    subprocess.run(["systemctl", "--user", "restart", "face-guardian.service"], check=True)
                    log.info("Service RESTART successful.")
                else:
                    log.info("Stopping face-guardian.service...")
                    subprocess.run(["systemctl", "--user", "stop", "face-guardian.service"], check=False)
                    log.info("Service STOP successful.")
            except Exception as e:
                log.error(f"Service error: {e}")
            
            # 3. Show success toast immediately
            toast = Adw.Toast.new("✅ Settings Applied!")
            toast.set_timeout(3)
            GLib.idle_add(self.toast_overlay.add_toast, toast)
            GLib.idle_add(self.apply_btn.set_sensitive, True)
            log.info("================ END APPLY ===============")

        threading.Thread(target=task, daemon=True).start()

    def run_pkexec_command(self, cmd_list):
        # Using pkexec so the user gets a secure system popup asking for password
        # when performing privileged actions (enrollment needs camera and to write to /etc/)
        log.debug(f"Attempting pkexec command: {cmd_list}")
        try:
            # We explicitly need pkexec to spawn its graphical dialog
            full_cmd = ["pkexec"] + cmd_list
            
            # Set Wayland/X11 environment variables so pkexec apps can open Qt/GTK windows
            # and so polkit knows which display to show the password prompt on
            env = os.environ.copy()
            uid = os.getuid()
            if "XDG_RUNTIME_DIR" not in env:
                env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            
            log.debug(f"Environment for pkexec: DISPLAY={env.get('DISPLAY')}, XDG_RUNTIME_DIR={env.get('XDG_RUNTIME_DIR')}")
                
            # Use timeout=30 to prevent the thread from blocking forever
            # if the polkit dialog doesn't appear
            result = subprocess.run(full_cmd, env=env, check=True, timeout=30)
            log.info(f"pkexec command successful: {cmd_list}")
            return True
        except subprocess.TimeoutExpired:
            log.warning(f"pkexec timed out after 30s (password dialog may not be visible): {cmd_list}")
            return False
        except subprocess.CalledProcessError as e:
            log.warning(f"pkexec failed (user likely canceled password prompt): {e}")
            return False
        except Exception as e:
            log.error(f"Unexpected error executing pkexec command: {e}")
            return False

if __name__ == "__main__":
    app = FaceUnlockSettings()
    app.run(sys.argv)
