import sys
import subprocess
import os
import gobject

# commands
LCD_CLEARDISPLAY = '\014'
LCD_RETURNHOME = '\033[H'
LCD_XY = '\033[Lx%dy%d;'
LCD_BACKLIGHT_ON = '\033[L+'
LCD_BACKLIGHT_OFF = '\033[L-'

# define character
ICON_SUN = '\033[LG000150E1B0E150000;'
ICON_SINE = '\033[LG10008141405050200;'
ICON_LEFT = '\033[LG20004081F08040000;'
ICON_RIGHT = '\033[LG30004021F02040000;'
ICON_BAT = '\033[LG40E1B111111111F00;'
ICON_ALARM = '\033[LG500040E0E0E0E1F04;'

class Lcd(object):
	#initializes objects and lcd
	def __init__(self, lcd_dev):
		self.lcd = os.open(lcd_dev, os.O_WRONLY)
		self._backlight_on = self._backlight_state = True
		self._flashing = False

		# Add icons
		self.write(ICON_SUN)
		self.write(ICON_SINE)
		self.write(ICON_LEFT)
		self.write(ICON_RIGHT)
		self.write(ICON_BAT)
		self.write(ICON_ALARM)

		# Create a timer for backlight flashing
		gobject.timeout_add(500, self._flash)

	def write(self, data):
		os.write(self.lcd, data)

	def home(self):
		self.write(LCD_XY % (0, 0))

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
		self._backlight_on = v = bool(v)
		# When flashing, the backlight is under the control of the _flash
		# timer event. Stay out of it in that case.
		if not self.flashing:
			if v:
				self.backlight_on()
			else:
				self.backlight_off()

	def backlight_on(self):
		self._backlight_state = True
		self.write(LCD_RETURNHOME)
		self.write(LCD_BACKLIGHT_ON)

	def backlight_off(self):
		self._backlight_state = False
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

	@property
	def flashing(self):
		return self._flashing

	@flashing.setter
	def flashing(self, v):
		self._flashing = bool(v)
		if not (self._flashing and self.on):
			# Restore backlight to former state
			self.on = self._backlight_on

	def _flash(self):
		if self._flashing:
			if self._backlight_state:
				self.backlight_off()
			else:
				self.backlight_on()
		return True

	def splash(self):
		try:
			product = subprocess.check_output(["product-name"]).strip()
		except OSError:
			product = "---"
		self.on = True
		self.write(' Victron Energy \n' + product.center(16))

class DebugLcd(Lcd):
	def __init__(self):
		self._backlight_on = True
		self._flashing = False
		self.lcd = sys.stdout.fileno()

	def write(self, data):
		import re
		os.write(self.lcd, '\033[0m')
		# Set blinking to indicate flashing
		if self._flashing:
			os.write(self.lcd, '\033[5m')
		else:
			if self._backlight_on:
				os.write(self.lcd, '\033[1m')
			else:
				os.write(self.lcd, '\033[2m')
		os.write(self.lcd, re.sub('[\000\001\002\003\004\005]', '&', data))

	def home(self):
		self.write(LCD_RETURNHOME)

	@property
	def on(self):
		return self._backlight_on

	@on.setter
	def on(self, v):
		self._backlight_on = bool(v)

	@property
	def daylight(self):
		return True

	def clear(self):
		# VT100 clear sequence
		self.write('\033[3J\033[H\033[2J')

	def display_string(self, string, line):
		# VT100 sequence for goto-XY
		self.write('\033[{};{}f'.format(line, 1))
		self.write(string)
