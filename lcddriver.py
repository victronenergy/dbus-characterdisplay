import sys
import subprocess
import os

# commands
LCD_CLEARDISPLAY = '\014'
LCD_RETURNHOME = '\033[H'
LCD_XY = '\033[Lx%dy%d;'
LCD_BACKLIGHT_ON = '\033[L+'
LCD_BACKLIGHT_OFF = '\033[L-'

class Lcd(object):
	#initializes objects and lcd
	def __init__(self, lcd_dev):
		self.lcd = os.open(lcd_dev, os.O_WRONLY)
		self._backlight_on = True

	def write(self, data):
		os.write(self.lcd, data)

	# put string function
	def display_string(self, string, line):
		self.write(LCD_XY % (0, line - 1))
		self.write(string)

	# clear lcd and set to home
	def clear(self):
		self.write(LCD_CLEARDISPLAY)

	@property
	def on(self):
		return self._backlight_on

	@on.setter
	def on(self, v):
		self._backlight_on = bool(v)
		if v:
			self.write(LCD_RETURNHOME)
			self.write(LCD_BACKLIGHT_ON)
		else:
			self.write(LCD_BACKLIGHT_OFF)

	@property
	def daylight(self):
		""" Read the light sensor and return true if high level of ambient
		    light is detected. """
		try:
			return open(
				'/dev/gpio/display_sensor/value', 'rb').read().strip() == '0'
		except IOError:
			pass
		return True

	def splash(self):
		product = subprocess.check_output(["product-name"]).strip()
		self.on = True
		self.display_string(' Victron Energy ', 1)
		self.display_string(product.center(16), 2)

class DebugLcd(Lcd):
	def __init__(self):
		pass

	def display_string(self, string, line):
		if line == 1:
			print '|' + '-'*16 + '|'
		print '|' + string + '|'

	@property
	def on(self):
		pass

	@on.setter
	def on(self, v):
		pass

	@property
	def daylight(self):
		return True
