import logging
from functools import partial
from itertools import count, izip
from collections import defaultdict
from cache import smart_dict
import dbus

DISPLAY_COLS = 16
DISPLAY_ROWS = 2

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
							ip_params[key] = str(props[param])

	return ip_params


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


class Page(object):
	# Subclasses can override
	_auto = True

	def __init__(self):
		self.cache = smart_dict()
		self.watches = defaultdict(list)

	@property
	def auto(self):
		""" Returns true if this screen should be shown as part
		    of the automatically looping slideshow. If you return
			false screen can only be reached using the button. """
		return self._auto

	def unwrap_dbus_value(self, val):
		# Converts D-Bus values back to the original type. For example if val is of type DBus.Double, a float will be returned.
		if isinstance(val, (dbus.Int32, dbus.UInt32, dbus.Byte, dbus.Int16, dbus.UInt16, dbus.UInt32, dbus.Int64, dbus.UInt64)):
			return int(val)
		if isinstance(val, dbus.Double):
			return float(val)
		if isinstance(val, dbus.String):
			return str(val)

		return val


	def update_cache(self, key, v):
		if isinstance(v, dbus.Dictionary):
			value = v["Value"]
		elif isinstance(v, dbus.Array):
			value = None
		else:
			value = v

		if isinstance(value, dbus.Array):
			value = None

		self.cache[key] = self.unwrap_dbus_value(value)

	def query(self, conn, service, path):
		try:
			return conn.call_blocking(service, path, None, "GetValue", '', [])
		except:
			return None

	def track(self, conn, service, path, target):

		# Initialise cache values
		self.update_cache(target, self.query(conn, service, path))

		# If there are values on dbus update cache after property change
		self.watches[service].append((target, conn.add_signal_receiver(
			partial(self.update_cache, target),
			dbus_interface='com.victronenergy.BusItem',
			signal_name='PropertiesChanged',
			path=path,
			bus_name=service
		)))

	def cleanup(self, name):
		if name in self.watches:
			for target, w in self.watches[name]:
				w.remove()
				self.update_cache(target, None)
			del self.watches[name]

	def setup(self, conn, name):
		pass

	def get_text(self, conn):
		return [["", ""], ["", ""]]

	def display(self, conn, lcd):
		try:
			text = self.get_text(conn)
		except Exception, e:
			logging.exception("Exception showing page")
			return False

		if text is None:
			return False

		# Display text
		for row in xrange(0, DISPLAY_ROWS):
			line = format_line(text[row])
			lcd.display_string(line, row + 1)

		return True

class StatusPage(Page):
	states = {
        0x00: "Off",
        0x01: "Low Power",
        0x02: "Fault",
        0x03: "Bulk",
        0x04: "Absorption",
        0x05: "Float",
        0x06: "Storage",
        0x07: "Equalize",
        0x08: "Passthru",
        0x09: "Invert",
        0x0A: "Assist",
        0x0B: "Psu",
        0x100: "Discharge",
        0x101: "Sustain",
        0x102: "Recharge",
        0x103: "Sched Charge"
	}

	def __init__(self):
		super(StatusPage, self).__init__()
		self.cache.state = None
		self.cache.systemname = None

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, name, "/SystemState/State", "state")
			self.track(conn, name, "/SystemType", "systemtype")
		if name == "com.victronenergy.settings":
			self.track(conn, name, "/Settings/SystemSetup/SystemName", "systemname")

	def format(self, text):
		return "{:^{width}s}".format(text, width=DISPLAY_COLS)

	def get_text(self, conn):
		# This page always returns something, so that the display always
		# displays something
		if self.cache.state is None:
			# This should only happen if systemcalc is dead
			return [["Wait..."], ["", ""]]

		return [[self.format(self.cache.systemname or self.cache.systemtype or "Status"), ""],
			[self.format(self.states.get(self.cache.state, None) or ""), ""]]

class ReasonPage(StatusPage):
	def __init__(self):
		super(ReasonPage, self).__init__()
		self.cache.systemname = None
		self.cache.bl = None

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, name, "/SystemState/BatteryLife", "bl")
			self.track(conn, name, "/SystemState/ChargeDisabled", "cd")
			self.track(conn, name, "/SystemState/DischargeDisabled", "dd")
			self.track(conn, name, "/SystemState/LowSoc", "ls")
			self.track(conn, name, "/SystemState/SlowCharge", "sc")
			self.track(conn, name, "/SystemState/UserChargeLimited", "ucl")
			self.track(conn, name, "/SystemState/UserDischargeLimited", "udl")
			self.track(conn, name, "/SystemType", "systemtype")
		if name == "com.victronenergy.settings":
			self.track(conn, name, "/Settings/SystemSetup/SystemName", "systemname")

	def get_text(self, conn):
		if self.cache.bl is None:
			# This should only happen if systemcalc is dead
			return None

		reasons = ("{:X}".format(reason) for reason, v in izip(count(1), (
			self.cache.ls, self.cache.bl,
			self.cache.cd, self.cache.dd, self.cache.sc, self.cache.ucl,
			self.cache.udl)) if v)
		reasons = ",".join(reasons)
		text = "#" + reasons if reasons else ""

		# Skip this page if no reasons to display
		if text:
			return [[self.format(self.cache.systemname or self.cache.systemtype or "Status"), ""],
				[self.format(text), ""]]
		return None


# TODO split this into a vebus errors and mppt errors page
# Keep track of last error and current one
# Put in a dictionary of errors and display the text
class VebusErrorPage(Page):
	errors = {
		1: "Phase failure",
		2: "Contact support",
		3: "Config error",
		4: "Missing devices",
		5: "Overvolt AC-Out",
		6: "Assistant error",
		7: "VE.Bus BMS error",
		10: "Time sync error",
		11: "Relay error",
		14: "Transmit error",
		16: "Dongle missing",
		17: "Master missing",
		18: "Overvolt AC-Out",
		22: "Obsolete device",
		24: "S/O protect",
		25: "F/W incompatible",
		26: "Internal error"
	}

	def __init__(self):
		super(VebusErrorPage, self).__init__()
		self.cache.vebus_error = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, "/VebusError", "vebus_error")

	def get_text(self, conn):
		if self.cache.vebus_error is not None and self.cache.vebus_error > 0:
			return [["VE.Bus error:", str(self.cache.vebus_error or 0)],
				[self.errors.get(self.cache.vebus_error, ""), ""]]

		# Skip this page if no error
		return None

class SolarErrorPage(Page):
	errors = {
		2: "V-Bat too high",
		3: "T-sense fail",
		4: "T-sense fail",
		5: "T-sense fail",
		6: "V-sense fail",
		7: "V-sense fail",
		8: "V-sense fail",
		17: "Overheat",
		18: "Over-current",
		20: "Max Bulk",
		21: "C-sense fail",
		26: "Terminal o/heat",
		28: "Power stage",
		33: "PV overvoltage",
		34: "PV over-current",
		38: "PV-in shutdown",
		39: "PV-in shutdown",
		65: "Comm. warning",
		66: "Incompatible dev",
		67: "BMS lost",
		114: "CPU hot",
		116: "Calibration lost",
		119: "Settings lost"
	}
	def __init__(self):
		super(SolarErrorPage, self).__init__()
		self.cache.mppt_error = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.solarcharger."):
			self.track(conn, name, "/ErrorCode", "mppt_error")

	def get_text(self, conn):
		if self.cache.mppt_error is not None and self.cache.mppt_error > 0:
			return [["MPPT error:", str(self.cache.mppt_error or 0)],
				[self.errors.get(self.cache.mppt_error, ""), ""]]

		# Skip this page if no error
		return None


class BatteryPage(Page):
	def __init__(self):
		super(BatteryPage, self).__init__()
		self.cache.battery_soc = None

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, name, "/Dc/Battery/Voltage", "battery_voltage")
			self.track(conn, name, "/Dc/Battery/Soc", "battery_soc")
			self.track(conn, name, "/Dc/Battery/Power", "battery_power")


	def get_text(self, conn):
		if self.cache.battery_soc is None:
			return None

		text = [["Battery:", ""], ["", ""]]
		text[0][1] = "{:.1f} %".format(self.cache.battery_soc)
		if (self.cache.battery_power is not None):
			text[1][0] = "{:+.0f} W".format(self.cache.battery_power)

		if (self.cache.battery_voltage is not None):
			text[1][1] = "{:.1f} V".format(self.cache.battery_voltage)
		return text

class SolarPage(Page):
	mppt_states = {
		0x00: 'Off',
		0x03: 'Bulk',
		0x04: 'Absorb',
		0x05: 'Float',
		0x06: 'Storage',
		0x07: 'Eqlz',
		0xfc: 'ESS'
	}

	def __init__(self):
		super(SolarPage, self).__init__()
		self.cache.mppt_connected = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.solarcharger."):
			self.track(conn, name, "/Connected", "mppt_connected")
			self.track(conn, name, "/State", "mppt_state")
			self.track(conn, name, "/Yield/Power", "pv_power")
			self.track(conn, name, "/Pv/V", "pv_voltage")


	def get_text(self, conn):
		# Skip page if no mppt connected
		if not self.cache.mppt_connected:
			return None

		text = [["Solar:", "unknown"], ["", ""]]
		if self.cache.mppt_state is not None:
			try:
				text[0][1] = self.mppt_states[self.cache.mppt_state]
			except KeyError:
				pass

		if self.cache.pv_power is not None:
			text[1][0] = "{:.0f} W".format(self.cache.pv_power)

		if (self.cache.pv_voltage is not None):
			text[1][1] = "{:.1f} V".format(self.cache.pv_voltage)

		return text

class AcPage(Page):
	sources = ["", "Grid", "Genset", "Shore"]

	def __init__(self):
		super(AcPage, self).__init__()
		self.cache.vebus_connected = None

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, name, "/Ac/ActiveIn/Source", "ac_source")

		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, "/Connected", "vebus_connected")
			self.track(conn, name, "/Ac/ActiveIn/Connected", "ac_available")
			self.track(conn, name, "/Ac/ActiveIn/P", "ac_power_in")
			self.track(conn, name, "/Ac/Out/P", "ac_power_out")

	def get_ac_source(self, x):
		try:
			return self.sources[x]
		except IndexError:
			return self.sources[0]

	def get_text(self, conn):
		text = [["NO AC DATA", ""], ["", ""]]
		if self.cache.vebus_connected != 1:
			return None

		if self.cache.ac_available is not None and self.cache.ac_source is not None:
			if self.cache.ac_available == 1:
				text[0][0] = "{}:".format(self.get_ac_source(self.cache.ac_source))
				text[0][1] = "{:+.0f} W".format(self.cache.ac_power_in)
			else:
				text[0][0] = "AC disconnected"
				text[0][1] = ""

			if self.cache.ac_power_out is not None:
				text[1][0] = "Output:"
				text[1][1] = "{:+.0f} W".format(self.cache.ac_power_out)

		return text

class AcPhasePage(Page):
	_auto = False

	def __init__(self, phase):
		super(AcPhasePage, self).__init__()
		self.phase = phase
		self.cache.ac_power = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, "/Ac/ActiveIn/L{}/P".format(self.phase), "ac_power")
			self.track(conn, name, "/Ac/ActiveIn/L{}/V".format(self.phase), "ac_voltage_out")

	def get_text(self, conn):
		if self.cache.ac_power is None:
			return None

		return [["L{} (in)".format(self.phase),
				"{:.0f} V".format(self.cache.ac_voltage_out)], [
				"Power:", "{:+.0f} W".format(self.cache.ac_power)]]

class AcOutPhasePage(AcPhasePage):
	def __init__(self, phase):
		super(AcOutPhasePage, self).__init__(phase)
		self.cache.ac_power = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, "/Ac/Out/L{}/P".format(self.phase), "ac_power")
			self.track(conn, name, "/Ac/Out/L{}/V".format(self.phase), "ac_voltage_out")

	def get_text(self, conn):
		if self.cache.ac_power is None:
			return None

		return [["L{} (out)".format(self.phase),
				"{:.0f} V".format(self.cache.ac_voltage_out)], [
				"Power:", "{:+.0f} W".format(self.cache.ac_power)]]

class LanPage(Page):
	def __init__(self):
		super(LanPage, self).__init__()
		self._auto = False

	def _get_text(self, conn, head, iface):
		text = [[head, ""], ["", ""]]
		ip_params = {}

		try:
			ip_params = get_ipparams(conn, iface)
		except:
			return None

		if "ipv6_method" in ip_params:
			text[0][1] = ip_params["ipv6_method"]
			text[1][0] = ip_params.get("ipv6_address", "")
		elif "ipv4_method" in ip_params:
			text[0][1] = ip_params["ipv4_method"]
			text[1][0] = ip_params.get("ipv4_address", "")
		else:
			return None

		return text

	def get_text(self, conn):
		return self._get_text(conn, "LAN IP:", "ethernet")

class WlanPage(LanPage):
	def get_text(self, conn):
		return self._get_text(conn, "WIFI IP:", "wifi")
