from functools import partial
from collections import defaultdict
from cache import smart_dict
import dbus

class Tracker(object):
	def __init__(self):
		self.cache = smart_dict()
		self.watches = defaultdict(list)

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
