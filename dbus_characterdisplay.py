#!/usr/bin/env python

from functools import partial
from collections import Mapping
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gobject
import lcddriver
import time
import signal
import sys

DISPLAY_COLS = 16
DISPLAY_ROWS = 2

screens = ['battery', 'solar', 'grid', 'lan_ip', 'wifi_ip']
screen_index = -1	

mppt_states = ['off', 'unknown', 'fault', 'bulk', 'absorpt', 'float']

lcd = None	# Display handler

class smart_dict(dict):
	# Dictionary that can be accessed via attributes.
	def __getattr__(self, k):
		try:
			v = self[k]
			if isinstance(v, Mapping):
				return self.__class__(v)
			return v
		except KeyError:
			raise AttributeError(k)
	def __setattr__(self, k, v):
		self[k] = v

# Module-level key-value store for tracked dbus values
cache = smart_dict()

		
def unwrap_dbus_value(val):
	# Converts D-Bus values back to the original type. For example if val is of type DBus.Double, a float will be returned.

	if isinstance(val, (dbus.Int32, dbus.UInt32, dbus.Byte, dbus.Int16, dbus.UInt16, dbus.UInt32, dbus.Int64, dbus.UInt64)):
		return int(val)
	if isinstance(val, dbus.Double):
		return float(val)
	if isinstance(val, dbus.String):
		return str(val)

	return val


def get_ipparams(conn, interface):
	# Fetch IP params from conmann dbus for given interface (ethernet, wifi)

	ip_params = {}
	manager = dbus.Interface(conn.get_object("net.connman", "/"), "net.connman.Manager")

	for path, properties in manager.GetServices():
		if path.startswith('/net/connman/service/' + interface):
			for ip_version in ['IPv4', 'IPv6']:
				if ip_version in properties:
					props = properties[ip_version]
					for param in ['Address', 'Method']:
						if param in props:
							key = "{}_{}".format(ip_version, param).lower()
							ip_params[key] = unwrap_dbus_value(props[param])

	return ip_params
					

def update_cache(key, v):
	if isinstance(v, dbus.Dictionary):
		value = v["Value"]
	elif isinstance(v, dbus.Array):
		value = None
	else:
		value = v
		
	if isinstance(value, dbus.Array):
		value = None
		
	cache[key] = unwrap_dbus_value(value)


def query(conn, service, path):
	try:
		return conn.call_blocking(service, path, None, "GetValue", '', [])
	except:
		return None


def track(conn, service, path, target):

	# Initialise cache values
	update_cache(target, query(conn, service, path))

	if(cache.get(target) is not None):

		# If there are values on dbus update cache after porperty change
		conn.add_signal_receiver(
			partial(update_cache, target),
			dbus_interface='com.victronenergy.BusItem',
			signal_name='PropertiesChanged',
			path=path,
			bus_name=service
		)
	else:
		# Retry every 10 secs data is available on dbus
		gobject.timeout_add(10000, partial(track, conn, service, path, target))
	

def roll_screens(conn):
	# Iterate through screens array by incrementing screen_index.
	global screen_index

	screen_index = (screen_index + 1) % len(screens)
	if (print_screen(conn, screens[screen_index])):
		# On error show next page
		roll_screens(conn)
        return True


def print_screen(conn, page):
	# Collect data, prepare output and print it on the display

	# Position:  ul  ur   ll  lr  (upper-left, ...)
	text = [["", ""],["", ""]]

	if (page == "battery"):
		text[0][0] = "Battery:"

		if (cache["battery_soc"] is not None):
			text[0][1] = "{:.1f} %".format(cache["battery_soc"])

			if (cache["battery_power"] is not None):
				text[1][0] = "{:+.0f} W".format(cache["battery_power"])

			if (cache["battery_voltage"] is not None):
				text[1][1] = "{:.1f} V".format(cache["battery_voltage"])
				
		else:
			text[0][1] = "NO DATA"
			text[1][0] = "Check Connection"
			
	
	if (page == "solar"):
		text[0][0] = "Solar:"

		if (cache["mppt_connected"] is None or cache["mppt_connected"] == 0):
			update_cache ("mppt_connected", query(conn, "com.victronenergy.solarcharger.ttyS1", "/Connected"))
		
		if (cache["mppt_connected"] == 1):
			if (cache["mppt_state"] is not None):
				if (0 <= cache["mppt_state"] <= 5):
					text[0][1] = "{}".format(mppt_states[cache["mppt_state"]])
				else:
					text[0][1] = "{}".format('unkown')
		
			if (cache["pv_power"] is not None):
				text[1][0] = "{:.0f} W".format(cache["pv_power"])

			if (cache["pv_voltage"] is not None):
				text[1][1] = "{:.1f} V".format(cache["pv_voltage"])				
		else:
			text[0][1] = "NO DATA"
			text[1][0] = "Check Connection"


	if (page == "grid"): 
		text[0][0] = "Grid:"

		if (cache["vebus_connected"] is None or cache["vebus_connected"] == 0):
			update_cache("vebus_connected", query(conn, "com.victronenergy.ttyS3", "/Connected"))

		if (cache["vebus_connected"] == 1):
			if (cache["grid_available"] is not None):
				if (cache["grid_available"] == 1):
					text[0][1] = "{}".format('connected')
				else:	
					text[0][1] = "{}".format('n/a')				

				if (cache["grid_power"] is not None):
					text[1][0] = "{:+.0f} W".format(cache["grid_power"])
					
				if (cache["grid_voltage"] is not None):
					text[1][1] = "{:.0f} V".format(cache["grid_voltage"])
		else:
			text[0][1] = "NO DATA"
			text[1][0] = "Check Connection"

			
	if (page == "lan_ip" or page == "wifi_ip"):

		ifdevices = {'lan_ip': 'ethernet', 'wifi_ip': 'wifi'}
		ip_params = {}

		try:
			ip_params = get_ipparams(conn, ifdevices[page])
		except:
			return -1

		if (not ip_params.has_key("ipv4_method") and not ip_params.has_key("ipv6_method")):
			return -2

		text[0][0] = page.upper().replace('_', ' ') + ':';

		for ip_version in ['ipv6', 'ipv4']:
			
			if (ip_params.get(ip_version + "_method") is not None):
				text[0][1] = "{}".format(ip_params[ip_version + "_method"])

			if (ip_params.get(ip_version + "_address") is not None):
				text[1][0] = "{}".format(ip_params[ip_version + "_address"])

		if (text[1][0] == ''):
			text[1][1] = "Not Connected"


	for row in range(0, DISPLAY_ROWS):
		line = format_line(text[row])
		lcd.lcd_display_string(line, row + 1)
	
		print '|' + line + '|'

	print '|' + '-'*DISPLAY_COLS + '|'

	return 0

	
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
