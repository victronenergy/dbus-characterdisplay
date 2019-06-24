import sys
import subprocess
import os
from time import time
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
		self._backlight_on = True
		self._flashing = False
		self._turned_on = time()

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
		self._backlight_on = bool(v)
		if v:
			self._turned_on = time()
			self.write(LCD_RETURNHOME)
			self.write(LCD_BACKLIGHT_ON)
		else:
			self.write(LCD_BACKLIGHT_OFF)

	@property
	def flashing(self):
		return self._flashing

	@flashing.setter
	def flashing(self, v):
		self._flashing = bool(v)
		if not (self._flashing and self.on):
			# Leave the screen on when we stop flashing
			self.on = True

	def _flash(self):
		if self._flashing:
			self.on = not self.on
		return True

	@property
	def on_time(self):
		return max(0, time() - self._turned_on)

	def splash(self):
		try:
			product = subprocess.check_output(["product-name"]).strip()
		except OSError:
			product = "---"
		self.on = True
		self.write(' Victron Energy \n' + product.center(16))

class DebugLcd(Lcd):
	FIFO = '/tmp/chardisp'
	def __init__(self):
		self._backlight_on = True
		self._flashing = False
		self._turned_on = time()
		self.lcd = sys.stdout.fileno()

	def write(self, data):
		import re
		os.write(self.lcd, re.sub('[\000\001\002\003\004\005]', '&', data))

	def home(self):
		self.write(LCD_RETURNHOME)

	@property
	def on(self):
		return self._backlight_on

	@on.setter
	def on(self, v):
		self._backlight_on = bool(v)

	def clear(self):
		# VT100 clear sequence
		self.write('\033[3J\033[H\033[2J')

	def display_string(self, string, line):
		# VT100 sequence for goto-XY
		self.write('\033[{};{}f'.format(line, 1))
		self.write(string)
