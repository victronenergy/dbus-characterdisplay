#!/usr/bin/env python

import time
import signal
import sys
from functools import partial
from itertools import cycle
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from evdev import InputDevice, ecodes
import gobject
import lcddriver
from cache import smart_dict
from pages import StatusPage, BatteryPage, SolarPage, AcPage, LanPage, WlanPage

ROLL_TIMEOUT = 5
DISPLAY_COLS = 16
DISPLAY_ROWS = 2

_screens = [StatusPage(), BatteryPage(), SolarPage(), AcPage(), LanPage(), WlanPage()]
screens = cycle(_screens)
lcd = None	# Display handler

def roll_screens(conn):
	text = None
	while text is None:
		text = screens.next().get_text(conn)

	# Display text
	for row in xrange(0, DISPLAY_ROWS):
		line = format_line(text[row])
		lcd.lcd_display_string(line, row + 1)

		print '|' + line + '|'
	print '|' + '-'*DISPLAY_COLS + '|'
	return True


def format_line(line):

	if (line and line[0] is not None):

		pad = DISPLAY_COLS - len(line[0])

		if (pad < 0):
			return ("{:.{}}").format(line[0], DISPLAY_COLS)
		elif (len(line[1]) > pad):
			return ("{}{:.{}}").format(line[0], line[1], pad)
		else:	
			return ("{}{:>{}}").format(line[0], line[1], pad)	

	return " "*DISPLAY_COLS


def main():
	DBusGMainLoop(set_as_default=True)

	global lcd

	conn = dbus.SystemBus()	# Initialize dbus connector
	lcd = lcddriver.Lcd()	# Get LCD display handler

	lcd.lcd_splash() 	# Show spash screen while initialization

	for screen in _screens:
		screen.setup(conn)

	# Keyboard handling
	try:
		kbd = InputDevice("/dev/input/by-path/platform-disp_keys-event")
	except OSError:
		kbd = None

	# Context object for event handlers
	ctx = smart_dict({'count': ROLL_TIMEOUT, 'kbd': kbd})

	if kbd is not None:
		def keypress(fd, condition, ctx):
			for event in ctx.kbd.read():
				# We could check for event.code == ecodes.KEY_LEFT but there
				# is only one button, so lets just make them all do the same.
				if event.type == ecodes.EV_KEY and event.value == 1:
					ctx.count = ROLL_TIMEOUT
					roll_screens(conn)
			return True

		gobject.io_add_watch(kbd.fd, gobject.IO_IN, keypress, ctx)

	def tick(ctx):
		if ctx.count == 0:
			roll_screens(conn)
		ctx.count = (ctx.count - 1) % ROLL_TIMEOUT
		return True

	gobject.timeout_add(1000, tick, ctx)

	gobject.MainLoop().run()


if __name__ == "__main__":
	main()
