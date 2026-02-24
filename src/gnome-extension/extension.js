import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { QuickToggle, SystemIndicator } from 'resource:///org/gnome/shell/ui/quickSettings.js';

let _indicator = null;
let _toggle = null;
let _updateTimeout = null;

const CONFIG_PATH = '/etc/face-unlock/config.conf';

function getGuardEnabled() {
  try {
    const [success, contents] = GLib.file_get_contents(CONFIG_PATH);
    if (success) {
      const lines = new TextDecoder().decode(contents).split('\n');
      for (let line of lines) {
        if (line.trim().startsWith('guard_enabled')) {
          return line.includes('true');
        }
      }
    }
  } catch (e) { }
  return false;
}

const FaceGuardToggle = class FaceGuardToggle extends QuickToggle {
  constructor() {
    super({
      title: 'Face Guard',
      iconName: 'changes-prevent-symbolic',
      toggleMode: true,
    });

    this.checked = getGuardEnabled();

    this.connect('clicked', () => {
      const newState = this.checked ? 'disable' : 'enable'; // Toggle since we are clicking it
      try {
        Gio.Subprocess.new(
          ['pkexec', '/usr/local/lib/face-unlock/toggle-guard.sh', newState],
          Gio.SubprocessFlags.NONE
        );
        // Keep UI checked state same artificially until config updates
        this.checked = !this.checked;
      } catch (e) {
        console.error(e);
      }
    });
  }
};

export default class FaceUnlockExtension {
  enable() {
    _indicator = new SystemIndicator();
    _toggle = new FaceGuardToggle();

    _indicator.quickSettingsItems.push(_toggle);
    Main.panel.statusArea.quickSettings.addExternalIndicator(_indicator);

    // Poll config periodically to sync toggle state if changed externally
    _updateTimeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
      if (_toggle) {
        _toggle.checked = getGuardEnabled();
      }
      return GLib.SOURCE_CONTINUE;
    });
  }

  disable() {
    if (_updateTimeout) {
      GLib.Source.remove(_updateTimeout);
      _updateTimeout = null;
    }
    if (_indicator) {
      _indicator.quickSettingsItems.forEach(item => item.destroy());
      _indicator.destroy();
      _indicator = null;
      _toggle = null;
    }
  }
}
