from functools import partial
from itertools import count, izip
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
	def __init__(self):
		self.cache = smart_dict()

		# Subclasses can override
		self._volatile = False

	@property
	def volatile(self):
		""" Returns true if this is a screen that should update often. """
		return self._volatile

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
		watches = []
		watches.append(conn.add_signal_receiver(
			partial(self.update_cache, target),
			dbus_interface='com.victronenergy.BusItem',
			signal_name='PropertiesChanged',
			path=path,
			bus_name=service
		))

		# Also track service movement
		def _track(name, old, new):
			for w in watches:
				w.remove()
			self.track(conn, service, path, target)

		watches.append(conn.add_signal_receiver(_track,
			signal_name='NameOwnerChanged',
			arg0=service))

	def setup(self, conn):
		pass

	def get_text(self, conn):
		return [["", ""], ["", ""]]

	def display(self, conn, lcd):
		text = self.get_text(conn)
		if text is None:
			return False

		# Display text
		for row in xrange(0, DISPLAY_ROWS):
			line = format_line(text[row])
			lcd.lcd_display_string(line, row + 1)

		return True

class StatusPage(Page):
	states = {
        0x00: "Off",
        0x01: "Low Pwr",
        0x02: "Fault",
        0x03: "Bulk",
        0x04: "Absorb",
        0x05: "Float",
        0x06: "Storage",
        0x07: "Equalize",
        0x08: "Passthru",
        0x09: "Invert",
        0x0A: "Assist",
        0x0B: "Psu",
        0x100: "Dischrg",
        0x101: "Sustain",
        0x102: "Recharge",
        0x103: "Sch Chrg"
	}


	def setup(self, conn):
		self.track(conn, "com.victronenergy.system", "/SystemState/State", "state")
		self.track(conn, "com.victronenergy.system", "/SystemState/BatteryLife", "bl")
		self.track(conn, "com.victronenergy.system", "/SystemState/ChargeDisabled", "cd")
		self.track(conn, "com.victronenergy.system", "/SystemState/DischargeDisabled", "dd")
		self.track(conn, "com.victronenergy.system", "/SystemState/LowSoc", "ls")
		self.track(conn, "com.victronenergy.system", "/SystemState/SlowCharge", "sc")
		self.track(conn, "com.victronenergy.system", "/SystemState/UserChargeLimited", "ucl")
		self.track(conn, "com.victronenergy.system", "/SystemState/UserDischargeLimited", "udl")

	def get_text(self, conn):
		text = [["Status:", "NO DATA"], ["Check Connection", ""]]
		state = self.states.get(self.cache.state, None)
		if state is not None:
			text[0][1] = state

		reasons = ("{:X}".format(reason) for reason, v in izip(count(1), (
			self.cache.ls, self.cache.bl,
			self.cache.cd, self.cache.dd, self.cache.sc, self.cache.ucl,
			self.cache.udl)) if v)
		reasons = ",".join(reasons)
		text[1][0] = "#" + reasons if reasons else ""

		return text

class ErrorPage(Page):
	def setup(self, conn):
		self.track(conn, "com.victronenergy.vebus.ttyS3", "/VebusError", "vebus_error")
		self.track(conn, "com.victronenergy.solarcharger.ttyS1", "/ErrorCode", "mppt_error")

	def get_text(self, conn):
		if self.cache.vebus_error or self.cache.mppt_error:
			return [["VE.Bus error:", str(self.cache.vebus_error or 0)],
				["  MPPT error:", str(self.cache.mppt_error or 0)]]

		# Skip this page if no error
		return None

class BatteryPage(Page):
	def __init__(self):
		super(BatteryPage, self).__init__()
		self._volatile = True

	def setup(self, conn):
		self.track(conn, "com.victronenergy.system", "/Dc/Battery/Voltage", "battery_voltage")
		self.track(conn, "com.victronenergy.system", "/Dc/Battery/Soc", "battery_soc")
		self.track(conn, "com.victronenergy.system", "/Dc/Battery/Power", "battery_power")


	def get_text(self, conn):
		text = [["Battery:", "NO DATA"], ["Check Connection", ""]]
		if self.cache.battery_soc is not None:
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

	def setup(self, conn):
		self.track(conn, "com.victronenergy.solarcharger.ttyS1", "/Connected", "mppt_connected")
		self.track(conn, "com.victronenergy.solarcharger.ttyS1", "/State", "mppt_state")
		self.track(conn, "com.victronenergy.solarcharger.ttyS1", "/Yield/Power", "pv_power")
		self.track(conn, "com.victronenergy.solarcharger.ttyS1", "/Pv/V", "pv_voltage")


	def get_text(self, conn):
		text = [["Solar:", "NO DATA"], ["Check Connection", ""]]
		if self.cache.mppt_connected == 1:
			if self.cache.mppt_state is not None:
				try:
					text[0][1] = self.mppt_states[self.cache.mppt_state]
				except KeyError:
					text[0][1] = "unknown"

			if self.cache.pv_power is not None:
				text[1][0] = "{:.0f} W".format(self.cache.pv_power)

			if (self.cache.pv_voltage is not None):
				text[1][1] = "{:.1f} V".format(self.cache.pv_voltage)

		return text

class AcPage(Page):
	sources = ["Unavailable", "Grid", "Generator", "Shore"]

	def __init__(self):
		super(AcPage, self).__init__()
		self._volatile = True

	def setup(self, conn):
		self.track(conn, "com.victronenergy.system", "/Ac/ActiveIn/Source", "ac_source")
		self.track(conn, "com.victronenergy.vebus.ttyS3", "/Connected", "vebus_connected")
		self.track(conn, "com.victronenergy.vebus.ttyS3", "/Ac/ActiveIn/Connected", "ac_available")
		self.track(conn, "com.victronenergy.vebus.ttyS3", "/Ac/ActiveIn/L1/P", "ac_power")
		self.track(conn, "com.victronenergy.vebus.ttyS3", "/Ac/ActiveIn/L1/V", "ac_voltage")

	def get_ac_source(self, x):
		try:
			return self.sources[x]
		except IndexError:
			return self.sources[0]

	def get_text(self, conn):
		text = [["AC:", "NO DATA"], ["Check Connection", ""]]
		if self.cache.vebus_connected == 1:
			if self.cache.ac_available is not None and self.cache.ac_source is not None:
				if self.cache.ac_available == 1:
					text[0][1] = self.get_ac_source(self.cache.ac_source)
				else:
					text[0][1] = "n/a"

				if self.cache.ac_power is not None:
					text[1][0] = "{:+.0f} W".format(self.cache.ac_power)

				if (self.cache.ac_voltage is not None):
					text[1][1] = "{:.0f} V".format(self.cache.ac_voltage)

		return text

class LanPage(Page):
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
