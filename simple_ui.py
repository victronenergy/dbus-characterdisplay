from itertools import izip
from evdev import ecodes


class cycle(object):
	""" Cyclical list-iterator that can be reset. """
	def __init__(self, li):
		self.li = li
		self.reset()
	def reset(self):
		self.iterable = iter(self.li)
	def next(self):
		try:
			return next(self.iterable)
		except StopIteration:
			self.reset()
			return next(self.iterable)
	def __iter__(self):
		return self
    

class SimpleUserInterface:

    ROLL_TIMEOUT = 5
    BACKLIGHT_TIMEOUT = 300

    def __init__(self, lcd, conn, kbd, static_screens):
        self.lcd = lcd
        self.conn = conn
        self.kbd = kbd
        self._screens = static_screens
        self.screen_cycle = cycle(self._screens)
        self.screen = None
        self.count = self.ROLL_TIMEOUT

    def start(self):
        pass

    def key_pressed(self):
        for event in self.kbd.read():
            # We could check for event.code == ecodes.KEY_LEFT but there
            # is only one button, so lets just make them all do the same.
            if event.type == ecodes.EV_KEY and event.value == 1:
                # If backlight is off, turn it on
                if self.lcd.on:
                    # When buttons are used, stay on selected screen longer
                    self.count = self.ROLL_TIMEOUT * 6
                else:
                    # Except when the backlight was off, then normal timeout.
                    self.count = self.ROLL_TIMEOUT
                    self.lcd.on = True
                    self.screen_cycle.reset()
                self.screen = self._roll_screens(False)
            
    def tick(self):
        if self.count == 0:
            self.screen = self._roll_screens(True)
            if self.lcd.on_time > self.BACKLIGHT_TIMEOUT:
                self.lcd.on = False
        elif self.screen is not None:
            # Update the screen text
            self.screen.display(self.conn, self.lcd)
        self.count = self.count - 1 if self.count > 0 else self.ROLL_TIMEOUT

    def _show_screen(self, screen):
        return screen.display(self.conn, self.lcd)

    def _roll_screens(self, auto):
        # Cheap way of avoiding infinite loop
        for screen, _ in izip(self.screen_cycle, self._screens):
            if auto and not screen.auto:
                continue
            if self._show_screen(screen):
                return screen
        return None


