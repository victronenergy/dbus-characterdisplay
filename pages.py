import logging
from functools import partial
from itertools import count, izip
from collections import defaultdict
from cache import smart_dict
from track import Tracker
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


class Page(Tracker):
	# Subclasses can override
	_auto = True

	@property
	def auto(self):
		""" Returns true if this screen should be shown as part
		    of the automatically looping slideshow. If you return
			false screen can only be reached using the button. """
		return self._auto

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
	def __init__(self):
		super(StatusPage, self).__init__()
		self.states = {
			0x00: _("Off"),
			0x01: _("Low Power"),
			0x02: _("Fault"),
			0x03: _("Bulk"),
			0x04: _("Absorption"),
			0x05: _("Float"),
			0x06: _("Storage"),
			0x07: _("Equalize"),
			0x08: _("Passthru"),
			0x09: _("Invert"),
			0x0A: _("Assist"),
			0x0B: _("Psu"),
			0x100: _("Discharge"),
			0x101: _("Sustain"),
			0x102: _("Recharge"),
			0x103: _("Sched Charge")
		}
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


class VebusAlarmsPage(Page):
	def __init__(self):
		super(VebusAlarmsPage, self).__init__()
		self.alarms = {
			"HighTemperature": _("High temp"),
			"LowBattery": _("Low battery"),
			"Overload": _("Overload"),
			"Ripple": _("High ripple"),
			"TemperatureSensor": _("Temp Sense"),
			"VoltageSensor": _("Volt sense"),
		}

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			for phase in xrange(1, 4):
				for alarm in ("HighTemperature", "LowBattery",
						"Overload", "Ripple"):
					path = "/Alarms/L{}/{}".format(phase, alarm)
					self.track(conn, name, path, path)
			for alarm in ("TemperatureSensor", "VoltageSensor"):
				path = "/Alarms/{}".format(alarm)
				self.track(conn, name, path, path)
				self.track(conn, name, path, path)

	def get_text(self, conn):
		alarms = []
		for alarm in ("HighTemperature", "LowBattery",
					"Overload", "Ripple"):
			paths = ["/Alarms/L{}/{}".format(phase, alarm) for phase in xrange(1, 4)]
			if any((self.cache.get(p, None) for p in paths)):
				alarms.append(alarm)

		for alarm in ("TemperatureSensor", "VoltageSensor"):
			if self.cache.get("/Alarms/{}".format(alarm), None):
				alarms.append(alarm)

		if alarms:
			return [["Alarm:", ""], [self.alarms.get(alarms[0], ""), ""]]

		return None


class VebusErrorPage(Page):
	def __init__(self):
		super(VebusErrorPage, self).__init__()
		self.errors = {
			1: _("Phase failure"),
			2: _("Contact support"),
			3: _("Config error"),
			4: _("Missing devices"),
			5: _("Overvolt AC-Out"),
			6: _("Assistant error"),
			7: _("VE.Bus BMS error"),
			10: _("Time sync error"),
			11: _("Relay error"),
			14: _("Transmit error"),
			16: _("Dongle missing"),
			17: _("Master missing"),
			18: _("Overvolt AC-Out"),
			22: _("Obsolete device"),
			24: _("S/O protect"),
			25: _("F/W incompatible"),
			26: _("Internal error")
		}
		self.cache.vebus_error = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, "/VebusError", "vebus_error")

	def get_text(self, conn):
		if self.cache.vebus_error is not None and self.cache.vebus_error > 0:
			return [[_("VE.Bus error") + ":", '#'+str(self.cache.vebus_error or 0)],
				[self.errors.get(self.cache.vebus_error, ""), ""]]

		# Skip this page if no error
		return None


class SolarErrorPage(Page):
	def __init__(self):
		super(SolarErrorPage, self).__init__()
		self.errors = {
			2: _("V-Bat too high"),
			3: _("T-sense fail"),
			4: _("T-sense fail"),
			5: _("T-sense fail"),
			6: _("V-sense fail"),
			7: _("V-sense fail"),
			8: _("V-sense fail"),
			17: _("Overheat"),
			18: _("Over-current"),
			20: _("Max Bulk"),
			21: _("C-sense fail"),
			26: _("Terminal o/heat"),
			28: _("Power stage"),
			33: _("PV overvoltage"),
			34: _("PV over-current"),
			38: _("PV-in shutdown"),
			39: _("PV-in shutdown"),
			65: _("Comm. warning"),
			66: _("Incompatible dev"),
			67: _("BMS lost"),
			114: _("CPU hot"),
			116: _("Calibration lost"),
			119: _("Settings lost")
		}
		self.cache.mppt_error = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.solarcharger."):
			self.track(conn, name, "/ErrorCode", "mppt_error")

	def get_text(self, conn):
		if self.cache.mppt_error is not None and self.cache.mppt_error > 0:
			return [[_("MPPT error") + ":", '#'+str(self.cache.mppt_error or 0)],
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

		text = [[_("Battery") + ":", ""], ["", ""]]
		text[0][1] = "{:.1f} %".format(self.cache.battery_soc)
		if (self.cache.battery_power is not None):
			text[1][0] = "{:+.0f} W".format(self.cache.battery_power)

		if (self.cache.battery_voltage is not None):
			text[1][1] = "{:.1f} V".format(self.cache.battery_voltage)
		return text

class DetailedBatteryPage(Page):
	def __init__(self):
		super(DetailedBatteryPage, self).__init__()
		self.cache.mppt_connected = None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.solarcharger."):
			self.track(conn, name, "/Connected", "mppt_connected")
			self.track(conn, name, "/Dc/0/Voltage", "battery_voltage")
			self.track(conn, name, "/Dc/0/Current", "battery_current")

	def get_text(self, conn):
		# Skip page if no mppt connected
		if not self.cache.mppt_connected:
			return None

		text = [[_("Battery") + ":", ""], ["", ""]]
		if self.cache.battery_voltage is not None:
			text[1][0] = "{:.1f} V".format(self.cache.battery_voltage)
		if (self.cache.battery_current is not None):
			text[1][1] = "{:.1f} A".format(self.cache.battery_current)
		return text


class SolarPage(Page):
	def __init__(self):
		super(SolarPage, self).__init__()
		self.mppt_states = {
			0x00: _('Off'),
			0x03: _('Bulk'),
			0x04: _('Absorb'),
			0x05: _('Float'),
			0x06: _('Storage'),
			0x07: _('Eqlz'),
			0xfc: _('ESS')
		}
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

		text = [[_("Solar") + ":", "unknown"], ["", ""]]
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

class SolarHistoryPage(Page):
	_auto = False

	def __init__(self, day):
		super(SolarHistoryPage, self).__init__()
		self.days = {
			0: _("Today"),
			1: _("Yesterday")
		}
		self.cache._yield = None
		self.day = day

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.solarcharger."):
			self.track(conn, name, "/History/Daily/{}/Yield".format(self.day), "_yield")

	def get_text(self, conn):
		if not self.cache._yield:
			return None

		return [[_("Yield"), self.days[self.day]],
			["{:0.2f} KWh".format(self.cache._yield), ""]]

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
				text[0][0] = _("AC disconnected")
				text[0][1] = ""

			if self.cache.ac_power_out is not None:
				text[1][0] = _("Output") + ":"
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

		return [["L{} (".format(self.phase) +_("in") + ")",
				"{:.0f} V".format(self.cache.ac_voltage_out)], [
				_("Power") + ":", "{:+.0f} W".format(self.cache.ac_power)]]

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

		return [["L{} (".format(self.phase) + _("out") + ")",
				"{:.0f} V".format(self.cache.ac_voltage_out)], [
				_("Power") + ":", "{:+.0f} W".format(self.cache.ac_power)]]

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
		return self._get_text(conn, _("LAN IP") + ":", "ethernet")

class WlanPage(LanPage):
	def get_text(self, conn):
		return self._get_text(conn, _("WIFI IP") + ":", "wifi")
