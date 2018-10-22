import sys
import os
from time import time

# LCD device
LCD_DEV = '/dev/lcd'

# commands
LCD_CLEARDISPLAY = '\014'
LCD_RETURNHOME = '\033[H'
LCD_XY = '\033[Lx%dy%d;'
LCD_BACKLIGHT_ON = '\033[L+'
LCD_BACKLIGHT_OFF = '\033[L-'

class Lcd(object):
	#initializes objects and lcd
	def __init__(self):
		self.lcd = os.open(LCD_DEV, os.O_WRONLY)
		self._backlight_on = True
		self._turned_on = time()

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
			self._turned_on = time()
			self.write(LCD_RETURNHOME)
			self.write(LCD_BACKLIGHT_ON)
		else:
			self.write(LCD_BACKLIGHT_OFF)

	@property
	def on_time(self):
		return max(0, time() - self._turned_on)

	def splash(self):
		self.on = True
		self.display_string(' Victron Energy ', 1)
		self.display_string('   EasySolar    ', 2)

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
