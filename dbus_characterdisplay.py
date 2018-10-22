#!/usr/bin/env python

import time
import signal
import sys
from argparse import ArgumentParser
from functools import partial
from itertools import cycle, izip
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from evdev import InputDevice, ecodes
import gobject
import lcddriver
from cache import smart_dict
from pages import StatusPage, BatteryPage, SolarPage, AcPage, LanPage, WlanPage, ErrorPage

ROLL_TIMEOUT = 5

_screens = [StatusPage(), ErrorPage(), BatteryPage(), SolarPage(), AcPage(), LanPage(), WlanPage()]
screens = cycle(_screens)

def show_screen(conn, screen, lcd):
	return screen.display(conn, lcd)

def roll_screens(conn, lcd, auto):
	# Cheap way of avoiding infinite loop
	for screen, _ in izip(screens, _screens):
		if auto and not screen.auto:
			continue
		if show_screen(conn, screen, lcd):
			return screen
	return None

def main():
	parser = ArgumentParser(description=sys.argv[0])
	parser.add_argument('--debug',
			help='Print to terminal instead of to /dev/lcd',
			default=False, action="store_true")
	args = parser.parse_args()


	DBusGMainLoop(set_as_default=True)

	# Initialize dbus connector
	conn = dbus.SystemBus()

	# Get LCD display handler
	lcd = lcddriver.DebugLcd() if args.debug else lcddriver.Lcd()

	# Show spash screen while initialization
	lcd.splash()

	for screen in _screens:
		screen.setup(conn)

	# Keyboard handling
	try:
		kbd = InputDevice("/dev/input/by-path/platform-disp_keys-event")
	except OSError:
		kbd = None

	# Context object for event handlers
	ctx = smart_dict({'count': ROLL_TIMEOUT, 'kbd': kbd, 'screen': None})

	if kbd is not None:
		def keypress(fd, condition, ctx):
			for event in ctx.kbd.read():
				# We could check for event.code == ecodes.KEY_LEFT but there
				# is only one button, so lets just make them all do the same.
				if event.type == ecodes.EV_KEY and event.value == 1:
					# When buttons are used, stay on selected screen longer
					ctx.count = ROLL_TIMEOUT * 6
					ctx.screen = roll_screens(conn, lcd, False)
			return True

		gobject.io_add_watch(kbd.fd, gobject.IO_IN, keypress, ctx)

	def tick(ctx):
		if ctx.count == 0:
			ctx.screen = roll_screens(conn, lcd, True)
		elif ctx.screen is not None and ctx.screen.volatile:
			# Update the screen text
			ctx.screen.display(conn, lcd)

		ctx.count = ctx.count - 1 if ctx.count > 0 else ROLL_TIMEOUT
		return True

	gobject.timeout_add(1000, tick, ctx)

	gobject.MainLoop().run()


if __name__ == "__main__":
	main()
