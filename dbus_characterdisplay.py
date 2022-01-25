#!/usr/bin/python3 -u

import sys
import logging
from os.path import basename, dirname, abspath
from os.path import join as pathjoin
from argparse import ArgumentParser
import subprocess
import gettext
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from evdev import InputDevice, ecodes
from gi.repository import GLib
import lcddriver
from cache import smart_dict
from pages import StatusPage, ReasonPage, BatteryPage, SolarPage, SolarHistoryPage, DetailedBatteryPage
from pages import AcPage, AcPhasePage, AcOutPhasePage
from pages import LanPage, WlanPage, VebusErrorPage, SolarErrorPage, VebusAlarmsPage
from four_button_ui import FourButtonUserInterface
from simple_ui import SimpleUserInterface

VERSION = 0.12
FOUR_BUTTON_DEVICES = [b'victronenergy,paygo']

# Set up i18n
gettext.install("messages",
	pathjoin(dirname(abspath(__file__)), "lang"))

_screens = [StatusPage(), ReasonPage(), VebusErrorPage(),
	VebusAlarmsPage(), AcPage(),
	AcPhasePage(1), AcOutPhasePage(1),
	AcPhasePage(2), AcOutPhasePage(2),
	AcPhasePage(3), AcOutPhasePage(3),
	BatteryPage(), SolarPage(), SolarErrorPage(),
	SolarHistoryPage(0), SolarHistoryPage(1),
	LanPage(), WlanPage()]


def main():
	parser = ArgumentParser(description=sys.argv[0])
	parser.add_argument('--debug',
			help='Print to terminal instead of to /dev/lcd',
			default=False, action="store_true")
	parser.add_argument('--lcd',
			help='Path to lcd device, default /dev/lcd',
			default='/dev/lcd')
	parser.add_argument('--version',
			help='Print the version to stdout',
			default=False, action="store_true")
	args = parser.parse_args()

	if args.version:
		print("{} v{}".format(basename(sys.argv[0]), VERSION))
		return

	logging.basicConfig(format="%(levelname)s %(message)s", level=logging.INFO)
	logging.info("Starting {} v{}".format(basename(sys.argv[0]), VERSION))

	DBusGMainLoop(set_as_default=True)

	# Initialize dbus connector
	conn = dbus.SystemBus()

	# Get LCD display handler
	lcd = lcddriver.DebugLcd() if args.debug else lcddriver.Lcd(args.lcd)

	# Show spash screen while initialization
	lcd.splash()

	# Check the type of device
	has_four_buttons = subprocess.check_output(["/usr/bin/board-compat"]).strip() in FOUR_BUTTON_DEVICES

	# Add the screens only needed on the four button version
	if has_four_buttons:
		_screens.append(DetailedBatteryPage())

	# Handle services that are already up
	for name in conn.list_names():
		if name.startswith("com.victronenergy."):
			for screen in _screens:
				screen.setup(conn, name)

	# watch name changes
	def name_owner_changed(name, old, new):
		if name.startswith('com.victronenergy.'):
			if old:
				for screen in _screens:
					screen.cleanup(name)
			if new:
				for screen in _screens:
					screen.setup(conn, name)

	conn.add_signal_receiver(name_owner_changed, signal_name='NameOwnerChanged')

	# Keyboard handling
	try:
		kbd = InputDevice("/dev/input/by-path/platform-disp_keys-event")
		kbd.grab()
	except (OSError, IOError):
		kbd = None

	if has_four_buttons:
		ui_handler = FourButtonUserInterface(lcd, conn, kbd, _screens)
	else:
		ui_handler = SimpleUserInterface(lcd, conn, kbd, _screens)

	ui_handler.start()

	if kbd is not None:
		def keypress(fd, condition):
			ui_handler.key_pressed()
			return True

		GLib.io_add_watch(kbd.fd, GLib.IO_IN, keypress)

	def tick():
		ui_handler.tick()
		return True

	GLib.timeout_add(1000, tick)

	GLib.MainLoop().run()


if __name__ == "__main__":
	main()
