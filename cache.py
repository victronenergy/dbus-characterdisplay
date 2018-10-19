from collections import Mapping

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
