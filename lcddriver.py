import sys
import subprocess
import os
from time import time

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
		self._turned_on = time()

		# Add icons
		self.write(ICON_SUN)
		self.write(ICON_SINE)
		self.write(ICON_LEFT)
		self.write(ICON_RIGHT)
		self.write(ICON_BAT)
		self.write(ICON_ALARM)

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
	def on_time(self):
		return max(0, time() - self._turned_on)

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

	def home(self):
		pass

	def write(self, data):
		print data

	@property
	def on(self):
		pass

	@on.setter
	def on(self, v):
		pass

	def clear(self):
		pass
