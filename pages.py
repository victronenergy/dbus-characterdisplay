import logging
from itertools import izip, cycle, islice
from collections import namedtuple, deque
from track import Tracker
import dbus

DISPLAY_COLS = 16
DISPLAY_ROWS = 2

Notification = namedtuple('Notification', ['type', 'device', 'message'])

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
		elif len(line) > 1:
			if (len(line[1]) > pad):
				return ("{}{:.{}}").format(line[0], line[1], pad)
			else:
				return ("{}{:>{}}").format(line[0], line[1], pad)

	return " "*DISPLAY_COLS

class Marquee(object):
	def __init__(self, s, size, pad=0):
		# Add some space so the screen clears before it restarts
		self.size = size # window size
		if len(s) > size:
			content = s + ' '*(pad+1)
			self.content = cycle(content)
		else:
			self.content = content = s
		self.slide = len(content) + 1

	def __str__(self):
		return "{:{size}.{size}s}".format(''.join(islice(self.content, self.slide)), size=self.size)

class TrackInstance(type):
	""" Enforces singleton behaviour on a class.  Adds a `instance` attribute
	    on the class object so the single item can be found quickly. """
	def __init__(klass, name, bases, attrs):
		if '_instance' not in klass.__dict__:
			klass._instance = None
		else:
			if klass._instance is not None:
				raise RuntimeError("Multiple instances of {}".format(klass.__name__))
			klass._instance = klass

	@property
	def instance(klass):
		return klass._instance

class Page(Tracker):
	__metaclass__ = TrackInstance

	# Subclasses can override
	_auto = True

	def __new__(klass, *args, **kwargs):
		klass._instance = super(Page, klass).__new__(klass, *args, **kwargs)
		return klass._instance

	@property
	def auto(self):
		""" Returns true if this screen should be shown as part
		    of the automatically looping slideshow. If you return
			false screen can only be reached using the button. """
		return self._auto

	def setup(self, conn, name):
		pass

	def key_pressed(self, ui, evt):
		""" If the page implements keypress behaviour, put that here.
		    Return False when no more events to handle. This can be used if a
		    dynamic page wants to react to user input. A page should always
		    eventually return False so that control can return to the main
		    loop. """
		return False

	@property
	def urgent(self):
		""" If this page has something urgent to display, this method should
			return True. This allows warning pages and notification pages to
		    hog the display by taking focus. """
		return False

	def get_text(self, conn):
		return ""

	def display(self, conn, lcd):
		try:
			text = self.get_text(conn)
		except Exception, e:
			logging.exception("Exception showing page")
			return False

		if text is None:
			return False

		# Display text
		if isinstance(text, (list, tuple)):
			for row, _line in izip(xrange(DISPLAY_ROWS), text):
				line = format_line(_line)
				lcd.display_string(line, row + 1)
		else:
			lcd.home()
			lcd.write(text)

		return True

	@classmethod
	def format_power(klass, p, w):
		_p = abs(p)
		def _inner():
			if _p >= 10000: # 10kw and above
				return "{}k".format(int(round(p/1000.0)))
			if _p >= 1000:
				return "{}k".format(round(p/1000.0, 1))
			return str(int(p))
		return "{:>{width}s}".format(_inner(), width=w)

	@classmethod
	def format_value(klass, v, p, u):
		""" Print v (a double) to precision p, and tack on the unit u. """
		return "{:.{precision}f}{}".format(v, u, precision=p)

class InverterInfoPage(Page):
	def __init__(self):
		super(InverterInfoPage, self).__init__()
		self.states = {
			0x00: _("Off"),
			0x01: _("LwP"),
			0x02: _("Flt"),
			0x03: _("Blk"),
			0x04: _("Abs"),
			0x05: _("Flt"),
			0x06: _("Sto"),
			0x07: _("Eql"),
			0x08: _("Pas"),
			0x09: _("Inv"),
			0x0A: _("Ast"),
			0x0B: _("Psu"),
			0x100: _("Dis"),
			0x101: _("Sus"),
			0x102: _("Rec"),
			0x103: _("Sch")
		}

		self.cache.batterypower = None
		self.cache.soc = None
		self.cache.state = None
		self.cache.hub = None
		self.solar_chargers = {}

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, "com.victronenergy.system", "/Ac/ConsumptionOnInput/L1/Power", "ac_in_l1")
			self.track(conn, "com.victronenergy.system", "/Ac/ConsumptionOnInput/L2/Power", "ac_in_l2")
			self.track(conn, "com.victronenergy.system", "/Ac/ConsumptionOnInput/L3/Power", "ac_in_l3")
			self.track(conn, "com.victronenergy.system", "/Ac/ConsumptionOnOutput/L1/Power", "ac_out_l1")
			self.track(conn, "com.victronenergy.system", "/Ac/ConsumptionOnOutput/L2/Power", "ac_out_l2")
			self.track(conn, "com.victronenergy.system", "/Ac/ConsumptionOnOutput/L3/Power", "ac_out_l3")

			# PV on AC
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnGrid/L1/Power", "pv_grid_l1")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnGrid/L2/Power", "pv_grid_l2")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnGrid/L3/Power", "pv_grid_l3")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnOutput/L1/Power", "pv_out_l1")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnOutput/L2/Power", "pv_out_l2")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnOutput/L3/Power", "pv_out_l3")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnGenset/L1/Power", "pv_genset_l1")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnGenset/L2/Power", "pv_genset_l2")
			self.track(conn, "com.victronenergy.system", "/Ac/PvOnGenset/L3/Power", "pv_genset_l3")

			# PV on DC
			self.track(conn, "com.victronenergy.system", "/Dc/Pv/Power", "pv_dc")

			# Battery info
			self.track(conn, "com.victronenergy.system", "/Dc/Battery/Power", "batterypower")
			self.track(conn, "com.victronenergy.system", "/Dc/Battery/Soc", "soc")

			# Overall state
			self.track(conn, "com.victronenergy.system", "/SystemState/State", "state")
			self.track(conn, "com.victronenergy.system", "/Hub", "hub")
		elif name.startswith("com.victronenergy.solarcharger."):
			# Track solar charger state, cause we might need it
			self.track(conn, name, "/State", name+'/State', self.update_solarchargers)

	def cleanup(self, name):
		super(InverterInfoPage, self).cleanup(name)
		k = name+'/State'
		if k in self.solar_chargers:
			del self.solar_chargers[k]

	def update_solarchargers(self, key, value):
		self.solar_chargers[key] = value

	@property
	def input_power(self):
		v = (self.cache.get(a) for a in ("ac_in_l1", "ac_in_l2", "ac_in_l3"))
		return sum(x for x in v if x is not None)

	@property
	def output_power(self):
		v = (self.cache.get(a) for a in ("ac_out_l1", "ac_out_l2", "ac_out_l3"))
		return sum(x for x in v if x is not None)

	@property
	def pv_power(self):
		v = (self.cache.get(a) for a in ("pv_grid_l1", "pv_grid_l2", "pv_grid_l3",
			"pv_out_l1", "pv_out_l2", "pv_out_l3",
			"pv_genset_l1", "pv_genset_l2", "pv_genset_l3", "pv_dc"))
		# Elaborate way of summing the items, but returning None if they are all None
		return reduce(lambda *args: None if all(a is None for a in args) else sum(a for a in args if a is not None), v)

	@property
	def charge_state(self):
		if self.cache.hub == 4:
			# This is an ESS system, we can show the overall state
			return self.cache.state

		# Multiple states might need consideration. Collect the state of the Multi and all
		# solar chargers.
		states = set([self.cache.state] + self.solar_chargers.values())

		# The states we care about are 3/Bulk, 4/Absorb, 7/Equalise, 5/Float
		# and 6/Storage. 7 is the only one out of order. Check for 7, then
		# simply select the max.
		if 7 in states: return 7
		return max(states) if states else None

	def get_text(self, conn):
		# First line:
		# 4 characters heading, 5 characters AC-in, space, 5 characters AC-out, W
		# Second line:
		# Bat symbol, 3 characters SoC, space, 5 characters battery power, W, Charge state
		return self.get_power_text() + "\n" + self.get_battery_text()

	def get_power_text(self):
		return "\001IO " + self.format_power(self.input_power, 5) + " " + self.format_power(self.output_power, 5) + "W"

	def get_pv_text(self):
		p = self.pv_power
		return "\000PV " + (self.format_power(p, 5) if p is not None else " --- ") + " " + self.format_power(self.output_power, 5) + "W"

	def get_battery_text(self):
		if None in (self.cache.batterypower, self.cache.state):
			return " "*DISPLAY_COLS
		return "\004" + \
			("{:>3.0f}%".format(self.cache.soc) if self.cache.soc is not None else '--  ') + \
			" " + self.format_power(self.cache.batterypower, 4) + "W " + \
			"{:>4}".format(self.states.get(self.charge_state, "---"))

class PVInfoPage(Page):
	""" Piggy-backs on InverterInfoPage, shows slightly alternate text. """
	def get_text(self, conn):
		if InverterInfoPage.instance is not None:
			return InverterInfoPage.instance.get_pv_text() + "\n" + \
				InverterInfoPage.instance.get_battery_text()

class BatteryPage(Page):
	_auto = False
	def __init__(self):
		super(BatteryPage, self).__init__()

		self.states = {
			0: _("Idle"),
			1: _("Charge"),
			2: _("Discharge")
		}

		self.cache.battery_state = None
		self.cache.battery_voltage = None
		self.cache.battery_power = None
		self.cache.battery_soc = None

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, name, "/Dc/Battery/Voltage", "battery_voltage")
			self.track(conn, name, "/Dc/Battery/Soc", "battery_soc")
			self.track(conn, name, "/Dc/Battery/Power", "battery_power")
			self.track(conn, name, "/Dc/Battery/State", "battery_state")


	def get_text(self, conn):
		return "\004{:>4s} {:>3s}% {:>4s}V\n".format(
			_("Bat"), str(int(self.cache.battery_soc)) if self.cache.battery_soc is not None else "---",
			str(round(self.cache.battery_voltage, 1)) if self.cache.battery_voltage is not None else "---") + \
			"{}W {:>10s}".format(self.format_power(self.cache.battery_power, 4) if self.cache.battery_power is not  None else "---", self.states.get(self.cache.battery_state, "---"))
		if self.cache.battery_state is None:
			return None

class SolarPage(Page):
	_auto = False
	def __init__(self):
		super(SolarPage, self).__init__()
		self.cache.pvp = None
		self._solar_yield = {}

	def setup(self, conn, name):
		if name == "com.victronenergy.system":
			self.track(conn, name, "/Dc/Pv/Current", "pvi")
			self.track(conn, name, "/Dc/Pv/Power", "pvp")
		if name.startswith("com.victronenergy.solarcharger."):
			self.track(conn, name, "/History/Daily/0/Yield", name+"/yield", self.update_solarchargers)

	def update_solarchargers(self, key, value):
		self._solar_yield[key] = value

	def cleanup(self, name):
		super(SolarPage, self).cleanup(name)
		k = name+'/yield'
		if k in self._solar_yield:
			del self._solar_yield[k]

	@property
	def solar_yield(self):
		return sum(v for v in self._solar_yield.itervalues() if v is not None)

	def get_text(self, conn):
		# Skip page if no mppt connected
		if self.cache.pvp is None:
			return None

		return "{} {:>4s}kWh {}\n".format(_("Solar"), str(int(round(self.solar_yield))), _("td")) + \
			self.format_power(self.cache.pvp, 4) + "W     " + "{:>6s}".format(self.format_value(self.cache.pvi or 0, 1, 'A'))

class AcSinglePhaseInPage(Page):
	_auto = False
	_path = "/Ac/ActiveIn"
	_heading = "ACin"

	def __init__(self):
		super(AcSinglePhaseInPage, self).__init__()
		self.cache.ac_voltage = None
		self.cache.ac_current = None

	@property
	def singlephase(self):
		if AcMultiPhaseVoltageInPage.instance is not None:
			return not AcMultiPhaseVoltageInPage.instance.multiphase
		return True # Assume true if that page is not initialised yet

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, self._path + "/L1/V", "ac_voltage")
			self.track(conn, name, self._path + "/L1/I", "ac_current")

	def format_value(self, v, p, u):
		if v is None: return '---'
		return super(AcSinglePhaseInPage, self).format_value(v, p, u)

	def get_text(self, conn):
		if not self.singlephase:
			return None
		iip = InverterInfoPage.instance
		return [[self._heading, self.format_power(iip.input_power, 5) + 'W'],
			[self.format_value(self.cache.ac_voltage, 0, 'V'),
			self.format_value(self.cache.ac_current, 1, 'A')]]

class AcSinglePhaseOutPage(AcSinglePhaseInPage):
	_path = "/Ac/Out"
	_heading = "ACout"

	@property
	def singlephase(self):
		if AcMultiPhaseVoltageOutPage.instance is not None:
			return not AcMultiPhaseVoltageOutPage.instance.multiphase
		return True # Assume true if that page is not initialised yet

class AcMultiPhaseVoltageInPage(Page):
	_auto = False
	_path = "/Ac/ActiveIn"
	_heading = "ACin "

	def __init__(self):
		super(AcMultiPhaseVoltageInPage, self).__init__()
		self.cache.vl1 = None
		self.cache.vl2 = None
		self.cache.vl3 = None

	@property
	def multiphase(self):
		return self.cache.vl2 is not None

	def setup(self, conn, name):
		if name.startswith("com.victronenergy.vebus."):
			self.track(conn, name, self._path + "/L1/V", "vl1")
			self.track(conn, name, self._path + "/L2/V", "vl2")
			self.track(conn, name, self._path + "/L3/V", "vl3")
			self.track(conn, name, self._path + "/L1/I", "il1")
			self.track(conn, name, self._path + "/L2/I", "il2")
			self.track(conn, name, self._path + "/L3/I", "il3")

	def get_text(self, conn):
		if not self.multiphase:
			return None
		return self._heading + " " + "(L1,L2,L3)\n"\
			"{:3d}V  {:3d}V  {:3d}V".format(int(self.cache.vl1 or 0),
			int(self.cache.vl2 or 0), int(self.cache.vl3 or 0))

class AcMultiPhaseVoltageOutPage(AcMultiPhaseVoltageInPage):
	_path = "/Ac/Out"
	_heading = "ACout"

class AcMultiPhaseCurrentInPage(Page):
	def format_value(self, v):
		if v >= 10:
			return "{:3d}A".format(int(v))
		return "{:3s}A".format(str(round(v, 1)))

	@property
	def data(self):
		return AcMultiPhaseVoltageInPage.instance

	def get_text(self, conn):
		data = self.data
		if not data: return None
		if not self.data.multiphase:
			return None
		return data._heading + " " + "(L1,L2,L3)\n" + \
			self.format_value(data.cache.il1 or 0) + "  " + \
			self.format_value(data.cache.il2 or 0) + "  " + \
			self.format_value(data.cache.il3 or 0)

class AcMultiPhaseCurrentOutPage(AcMultiPhaseCurrentInPage):
	@property
	def data(self):
		return AcMultiPhaseVoltageOutPage.instance

class NotificationsPage(Page):
	def __init__(self):
		super(NotificationsPage, self).__init__()
		self.notices = deque()

	def setup(self, conn, name):
		if name == "com.victronenergy.notifications":
			self.notifications_watch = conn.add_signal_receiver(self.add_notification,
				dbus_interface='com.victronenergy.Notifications',
				signal_name='NotificationAdded', path='/', bus_name=name)

			notifier = dbus.Interface(conn.get_object("com.victronenergy.notifications", "/"), "com.victronenergy.Notifications")
			for typ, device, desc, value in notifier.GetActiveNotifications():
				self.add_notification(typ, device, desc, value)

	@property
	def urgent(self):
		""" If there are notices, it is urgent that we show them. """
		return bool(self.notices)

	def add_notification(self, _type, device, description, value):
		pad = len(device) - len(description)
		self.notices.append(Notification(_type,
			Marquee(device, DISPLAY_COLS-1, max(0, -pad)),
			Marquee(description, DISPLAY_COLS, max(0, pad))))

	def display(self, conn, lcd):
		if self.notices:
			notice = self.notices[0]
			lcd.flashing = True
			lcd.home()
			lcd.write("\005" + str(notice.device) + "\n")
			lcd.write(str(notice.message))
		return True

	def key_pressed(self, ui, evt):
		if self.notices:
			self.notices.popleft()
			if len(self.notices) > 0:
				self.display(None, ui.lcd)
				return True
			else:
				# We popped the last one, send acknowledge
				try:
					ui.conn.call_blocking("com.victronenergy.notifications", "/", "com.victronenergy.Notifications", "acknowledge", '', [])
				except dbus.exceptions.DBusException:
					pass
				ui.lcd.flashing = False

		return False

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
