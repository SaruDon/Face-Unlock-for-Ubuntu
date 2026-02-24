import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

def on_realize(widget):
    # Try to center after realizing
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor()
    if not monitor:
        monitor = display.get_monitor(0)
    geometry = monitor.get_geometry()
    
    # Calculate center
    width, height = widget.get_size()
    x = geometry.x + (geometry.width - width) // 2
    y = geometry.y + (geometry.height - height) // 2
    
    widget.move(x, y)
    print(f"Moving to {x}, {y}, Monitor size: {geometry.width}x{geometry.height}")

win = Gtk.Window()
win.set_title("Test Center")
win.set_default_size(380, 520)
win.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
win.set_type_hint(Gdk.WindowTypeHint.DIALOG)
win.set_keep_above(True)

box = Gtk.Box()
box.pack_start(Gtk.Label(label="Center me!"), True, True, 0)
win.add(box)

win.connect("destroy", Gtk.main_quit)
#win.connect("realize", on_realize)

win.show_all()
Gtk.main()
