import sys

import i2c_lib
from time import *

# LCD Address
ADDRESS = 0x20

# commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# DDRAM Adress
LCD_ROW1 = 0x80
LCD_ROW2 = 0xC0

En = 0b00000001 # Enable bit
Rw = 0b00000010 # Read/Write bit
Rs = 0b00000100 # Register select bit
Bl = 0b00001000 # Backlight on

class lcd:
   #initializes objects and lcd
   def __init__(self):
      self.lcd_device = i2c_lib.i2c_device(ADDRESS,0)

      self.lcd_device.write_cmd_arg(6,0)
      self.lcd_device.write_cmd_arg(7,0xF0)

      sleep(.05)

      self.lcd_write(LCD_FUNCTIONSET | LCD_2LINE | LCD_5x8DOTS | LCD_8BITMODE, 0)
      self.lcd_write(LCD_DISPLAYCONTROL | LCD_DISPLAYON, 0)
      self.lcd_write(LCD_CLEARDISPLAY, 0)
      self.lcd_write(LCD_ENTRYMODESET | LCD_ENTRYLEFT, 0)
      sleep(0.2)

   def lcd_write(self, data, is_data=1):
      self.lcd_device.write_cmd_arg(2,data)
      if is_data == 1:
          self.lcd_device.write_cmd_arg(3, En | Rs | Bl)
          sleep(.0005)
          self.lcd_device.write_cmd_arg(3, Rs | Bl)
      else:
          self.lcd_device.write_cmd_arg(3, En | Bl)
          sleep(.0005)
          self.lcd_device.write_cmd_arg(3, Bl) 
      sleep(.0001)
	
   # put string function
   def lcd_display_string(self, string, line):
      if line == 1:
         self.lcd_write(LCD_ROW1, 0)
      if line == 2:
         self.lcd_write(LCD_ROW2, 0)

      for char in string:
         self.lcd_write(ord(char))

   # clear lcd and set to home
   def lcd_clear(self):
      self.lcd_write(LCD_CLEARDISPLAY, 0)
      self.lcd_write(LCD_RETURNHOME, 0)

   def lcd_off(self):
      global Bl
      Bl = 0b00000000 # Backlight off
      self.lcd_clear()
      Bl = 0b00001000 # Backlight on

   def lcd_on(self):
      self.lcd_write(LCD_RETURNHOME, 0)

   def lcd_splash(self):
      self.lcd_on()
      self.lcd_display_string(' Victron Energy ', 1)
      self.lcd_display_string('   EasySolar    ', 2)
