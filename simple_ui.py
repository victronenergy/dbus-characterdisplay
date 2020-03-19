from itertools import izip
from evdev import ecodes
from time import time
from track import Tracker


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


class SimpleUserInterface(object):

    ROLL_TIMEOUT = 5

    def __init__(self, lcd, conn, kbd, static_screens):
        self.lcd = lcd
        self.conn = conn
        self.kbd = kbd
        self._screens = static_screens
        self.screen_cycle = cycle(self._screens)
        self.screen = None
        self.count = self.ROLL_TIMEOUT
        self._idle = False
        self._last_activity = time()

        # Attach to settings we care about
        self.settings = Tracker()
        self.settings.track(conn, "com.victronenergy.settings", "/Settings/Gui/DisplayOff", "displayoff")

    @property
    def idle(self):
        return self._idle

    @idle.setter
    def idle(self, b):
        if not b:
            self._last_activity = time()
        self._idle = bool(b)

    @property
    def idle_time(self):
        return max(0, time() - self._last_activity)

    def start(self):
        pass

    def key_pressed(self):
        for event in self.kbd.read():
            # We could check for event.code == ecodes.KEY_LEFT but there
            # is only one button, so lets just make them all do the same.
            if event.type == ecodes.EV_KEY and event.value == 1:
                backlight = self.lcd.daylight
                if backlight and not self.lcd.on:
                    # Backlight is off but should be on. Then also restart
                    # from first screen
                    self.count = self.ROLL_TIMEOUT
                    self.screen_cycle.reset()
                else:
                    # If button is being actively used, stay on the
                    # selected screen longer
                    self.count = self.ROLL_TIMEOUT if self.idle else self.ROLL_TIMEOUT * 6

                self.idle = False
                self.lcd.on = backlight
                self.screen = self._roll_screens(False)

    def tick(self):
        backlight = True
        if self.count == 0:
            self.screen = self._roll_screens(True)
            if self.idle_time > self.settings.cache.displayoff:
                self.idle = True
                backlight = False
        elif self.screen is not None:
            # Update the screen text
            self.screen.display(self.conn, self.lcd)
        self.count = self.count - 1 if self.count > 0 else self.ROLL_TIMEOUT

        # Manage the backlight. Short Circuit eval means daylight sensor
        # is only consulted if the backlight would be on
        if self.lcd.on:
            self.lcd.on = backlight and self.lcd.daylight

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
