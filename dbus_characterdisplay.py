#!/usr/bin/env python

import time
import signal
import sys
from functools import partial
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gobject
import lcddriver
from cache import update_cache
from pages import BatteryPage, SolarPage, GridPage, LanPage, WlanPage

DISPLAY_COLS = 16
DISPLAY_ROWS = 2

screens = [BatteryPage(), SolarPage(), GridPage(), LanPage(), WlanPage()]
#screens = ['battery', 'solar', 'grid', 'lan_ip', 'wifi_ip']
screen_index = -1	

mppt_states = ['off', 'unknown', 'fault', 'bulk', 'absorpt', 'float']

lcd = None	# Display handler

def query(conn, service, path):
	try:
		return conn.call_blocking(service, path, None, "GetValue", '', [])
	except:
		return None


def track(conn, service, path, target):

	# Initialise cache values
	update_cache(target, query(conn, service, path))

	# If there are values on dbus update cache after property change
	watches = []
	watches.append(conn.add_signal_receiver(
		partial(update_cache, target),
		dbus_interface='com.victronenergy.BusItem',
		signal_name='PropertiesChanged',
		path=path,
		bus_name=service
	))

	# Also track service movement
	def _track(name, old, new):
		for w in watches:
			w.remove()
		track(conn, service, path, target)

	watches.append(conn.add_signal_receiver(_track,
		signal_name='NameOwnerChanged',
		arg0=service))

def roll_screens(conn):
	# Iterate through screens array by incrementing screen_index.
	global screen_index

	screen_index = (screen_index + 1) % len(screens)
	screen = screens[screen_index]
	text = screen.get_text(conn)

	if text is None:
		roll_screens(conn)
		return True

	# Display text
	for row in range(0, DISPLAY_ROWS):
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

	# Track battery values from systemcalc
	track(conn, "com.victronenergy.system", "/Dc/Battery/Voltage", "battery_voltage")
	track(conn, "com.victronenergy.system", "/Dc/Battery/Soc", "battery_soc")
	track(conn, "com.victronenergy.system", "/Dc/Battery/Power", "battery_power")

	# Track solar values from MPPT
	track(conn, "com.victronenergy.solarcharger.ttyS1", "/Connected", "mppt_connected")
	track(conn, "com.victronenergy.solarcharger.ttyS1", "/State", "mppt_state")
	track(conn, "com.victronenergy.solarcharger.ttyS1", "/Yield/Power", "pv_power")
	track(conn, "com.victronenergy.solarcharger.ttyS1", "/Pv/V", "pv_voltage")

	# Track grid values from Multi
	track(conn, "com.victronenergy.vebus.ttyS3", "/Connected", "vebus_connected")
	track(conn, "com.victronenergy.vebus.ttyS3", "/Ac/ActiveIn/Connected", "grid_available")
	track(conn, "com.victronenergy.vebus.ttyS3", "/Ac/ActiveIn/L1/P", "grid_power")
	track(conn, "com.victronenergy.vebus.ttyS3", "/Ac/ActiveIn/L1/V", "grid_voltage")	

	gobject.timeout_add(10000, partial(roll_screens, conn))

	gobject.MainLoop().run()


if __name__ == "__main__":
	main()
