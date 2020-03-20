#!/usr/bin/env python

import sys
import logging
from os import environ
from os.path import basename, dirname, abspath
from os.path import join as pathjoin
from argparse import ArgumentParser
import subprocess
import gettext
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from evdev import InputDevice, ecodes
import gobject
import lcddriver
from cache import smart_dict
from pages import BatteryPage, SolarPage
from pages import AcSinglePhaseInPage, AcSinglePhaseOutPage
from pages import AcMultiPhaseVoltageInPage, AcMultiPhaseVoltageOutPage
from pages import AcMultiPhaseCurrentInPage, AcMultiPhaseCurrentOutPage
from pages import LanPage, WlanPage
from pages import InverterInfoPage, PVInfoPage
from four_button_ui import FourButtonUserInterface
from simple_ui import SimpleUserInterface

VERSION = 0.6
FOUR_BUTTON_DEVICES = ['victronenergy,paygo']

# Set up i18n
gettext.install("messages",
	pathjoin(dirname(abspath(__file__)), "lang"), unicode=True)

_screens = [InverterInfoPage(), PVInfoPage(), AcSinglePhaseInPage(), AcSinglePhaseOutPage(),
	AcMultiPhaseVoltageInPage(), AcMultiPhaseVoltageOutPage(), AcMultiPhaseCurrentInPage(),
	AcMultiPhaseCurrentOutPage(), SolarPage(), BatteryPage(), LanPage(), WlanPage()]

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
		print "{} v{}".format(basename(sys.argv[0]), VERSION)
		return

	logging.basicConfig(format="%(levelname)s %(message)s", level=logging.INFO)
	logging.info("Starting {} v{}".format(basename(sys.argv[0]), VERSION))

	DBusGMainLoop(set_as_default=True)

	# Initialize dbus connector
	conn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in environ else dbus.SystemBus()

	# Get LCD display handler
	lcd = lcddriver.DebugLcd() if args.debug else lcddriver.Lcd(args.lcd)

	# Show spash screen while initialization
	lcd.clear()
	lcd.splash()

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
	except OSError:
		if args.debug:
			import termios
			from evdev.events import InputEvent
			class DebugKeyboard(object):
				fd = sys.stdin
				def read(self):
					termios.tcflush(sys.stdin, termios.TCIFLUSH)
					return (InputEvent(0, 0, ecodes.EV_KEY, ecodes.KEY_LEFT, 1),)
			kbd = DebugKeyboard()
		else:
			kbd = None

	try:
		has_four_buttons = subprocess.check_output(["/usr/bin/board-compat"]).strip() in FOUR_BUTTON_DEVICES
	except OSError:
		has_four_buttons = False

	if has_four_buttons:
		ui_handler = FourButtonUserInterface(lcd, conn, kbd, _screens)
	else:
		ui_handler = SimpleUserInterface(lcd, conn, kbd, _screens)

	ui_handler.start()

	if kbd is not None:
		def keypress(fd, condition):
			ui_handler.key_pressed()
			return True

		gobject.io_add_watch(kbd.fd, gobject.IO_IN, keypress)

	def tick():
		ui_handler.tick()
		return True

	gobject.timeout_add(1000, tick)

	gobject.MainLoop().run()


if __name__ == "__main__":
	main()
