import sys
import os

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

	def write(self, data):
		os.write(self.lcd, data)

	# put string function
	def display_string(self, string, line):
		self.write(LCD_XY % (0, line - 1))
		self.write(string)

	# clear lcd and set to home
	def clear(self):
		self.write(LCD_CLEARDISPLAY)

	def off(self):
		self.clear()
		self.write(LCD_BACKLIGHT_OFF)

	def on(self):
		self.write(LCD_RETURNHOME)
		self.write(LCD_BACKLIGHT_ON)

	def splash(self):
		self.on()
		self.display_string(' Victron Energy ', 1)
		self.display_string('   EasySolar    ', 2)

class DebugLcd(Lcd):
	def __init__(self):
		pass

	def display_string(self, string, line):
		if line == 1:
			print '|' + '-'*16 + '|'
		print '|' + string + '|'

	def lcd_off(self):
		pass

	def on(self):
		pass
