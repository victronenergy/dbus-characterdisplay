#!/usr/bin/env python

import time
import signal
import sys
import logging
from os.path import basename
from argparse import ArgumentParser
from functools import partial
from itertools import izip
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from evdev import InputDevice, ecodes
import gobject
import lcddriver
from cache import smart_dict
from pages import StatusPage, ReasonPage, BatteryPage, SolarPage
from pages import AcPage, AcPhasePage, AcOutPhasePage
from pages import LanPage, WlanPage, VebusErrorPage, SolarErrorPage

VERSION = 0.1
ROLL_TIMEOUT = 5
BACKLIGHT_TIMEOUT = 300

_screens = [StatusPage(), ReasonPage(), VebusErrorPage(), SolarErrorPage(),
	BatteryPage(), SolarPage(), AcPage(),
	AcPhasePage(1), AcOutPhasePage(1),
	AcPhasePage(2), AcOutPhasePage(2),
	AcPhasePage(3), AcOutPhasePage(3),
	LanPage(), WlanPage()]

class cycle(object):
	""" Cyclical list-iterator that can be reset. """
	def __init__(self, li):
		self.li = li
		self.reset()
	def reset(self):
		self.iterable = iter(self.li)
	def next(self):
		try:
			return next(self.iterable)
		except StopIteration:
			self.reset()
			return next(self.iterable)
	def __iter__(self):
		return self

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
	conn = dbus.SystemBus()

	# Get LCD display handler
	lcd = lcddriver.DebugLcd() if args.debug else lcddriver.Lcd(args.lcd)

	# Show spash screen while initialization
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
		kbd = None

	# Context object for event handlers
	ctx = smart_dict({'count': ROLL_TIMEOUT, 'kbd': kbd, 'screen': None})

	if kbd is not None:
		def keypress(fd, condition, ctx):
			for event in ctx.kbd.read():
				# We could check for event.code == ecodes.KEY_LEFT but there
				# is only one button, so lets just make them all do the same.
				if event.type == ecodes.EV_KEY and event.value == 1:
					# If backlight is off, turn it on
					if lcd.on:
						# When buttons are used, stay on selected screen longer
						ctx.count = ROLL_TIMEOUT * 6
					else:
						# Except when the backlight was off, then normal timeout.
						ctx.count = ROLL_TIMEOUT
						lcd.on = True
						screens.reset()

					ctx.screen = roll_screens(conn, lcd, False)

			return True

		gobject.io_add_watch(kbd.fd, gobject.IO_IN, keypress, ctx)

	def tick(ctx):
		# No need to update if the backlight is off
		if not lcd.on:
			return True

		if ctx.count == 0:
			ctx.screen = roll_screens(conn, lcd, True)
			if lcd.on_time > BACKLIGHT_TIMEOUT:
				lcd.on = False
		elif ctx.screen is not None:
			# Update the screen text
			ctx.screen.display(conn, lcd)

		ctx.count = ctx.count - 1 if ctx.count > 0 else ROLL_TIMEOUT
		return True

	gobject.timeout_add(1000, tick, ctx)

	gobject.MainLoop().run()


if __name__ == "__main__":
	main()
