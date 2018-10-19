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

	def lcd_write(self, data):
		os.write(self.lcd, data)

	# put string function
	def lcd_display_string(self, string, line):
		self.lcd_write(LCD_XY % (0, line - 1))
		self.lcd_write(string)

	# clear lcd and set to home
	def lcd_clear(self):
		self.lcd_write(LCD_CLEARDISPLAY)

	def lcd_off(self):
		self.lcd_clear()
		self.lcd_write(LCD_BACKLIGHT_OFF)

	def lcd_on(self):
		self.lcd_write(LCD_RETURNHOME)
		self.lcd_write(LCD_BACKLIGHT_ON)

	def lcd_splash(self):
		self.lcd_on()
		self.lcd_display_string(' Victron Energy ', 1)
		self.lcd_display_string('   EasySolar    ', 2)

class DebugLcd(Lcd):
	def __init__(self):
		pass

	def lcd_display_string(self, string, line):
		if line == 1:
			print '|' + '-'*16 + '|'
		print '|' + string + '|'

	def lcd_off(self):
		pass

	def lcd_on(self):
		pass
