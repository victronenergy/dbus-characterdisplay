from collections import Mapping
import dbus

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
