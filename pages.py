from cache import cache
from dbus import Interface

screens = ['battery', 'solar', 'grid', 'lan_ip', 'wifi_ip']
mppt_states = {
	0x00: 'Off',
	0x03: 'Bulk',
	0x04: 'Absorb',
	0x05: 'Float',
	0x06: 'Storage',
	0x07: 'Eqlz',
	0xfc: 'ESS'
}

def get_ipparams(conn, interface):
	# Fetch IP params from conmann dbus for given interface (ethernet, wifi)

	ip_params = {}
	manager = Interface(conn.get_object("net.connman", "/"), "net.connman.Manager")

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
					


class Page(object):
	def get_text(self, conn):
		return [["", ""], ["", ""]]

class BatteryPage(Page):
	key = "battery"

	def get_text(self, conn):
		text = [["Battery:", "NO DATA"], ["Check Connection", ""]]
		if cache.battery_soc is not None:
			text[0][1] = "{:.1f} %".format(cache.battery_soc)
			if (cache.battery_power is not None):
				text[1][0] = "{:+.0f} W".format(cache.battery_power)

			if (cache.battery_voltage is not None):
				text[1][1] = "{:.1f} V".format(cache.battery_voltage)
		return text

class SolarPage(Page):
	key = "solar"

	def get_text(self, conn):
		text = [["Solar:", "NO DATA"], ["Check Connection", ""]]
		if cache.mppt_connected == 1:
			if cache.mppt_state is not None:
				try:
					text[0][1] = mppt_states[cache.mppt_state]
				except KeyError:
					text[0][1] = "unknown"
		
			if cache.pv_power is not None:
				text[1][0] = "{:.0f} W".format(cache.pv_power)

			if (cache.pv_voltage is not None):
				text[1][1] = "{:.1f} V".format(cache.pv_voltage)				

		return text

class GridPage(Page):
	key = "grid"

	def get_text(self, conn):
		text = [["Grid:", "NO DATA"], ["Check Connection", ""]]
		if cache.vebus_connected == 1:
			if cache.grid_available is not None:
				if cache.grid_available == 1:
					text[0][1] = "connected"
				else:	
					text[0][1] = "n/a"

				if cache.grid_power is not None:
					text[1][0] = "{:+.0f} W".format(cache.grid_power)
					
				if (cache.grid_voltage is not None):
					text[1][1] = "{:.0f} V".format(cache.grid_voltage)

		return text

class LanPage(Page):
	key = "lan_ip"

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
	key = "wifi_ip"

	def get_text(self, conn):
		return self._get_text(conn, "WIFI IP:", "wifi")
