from evdev import ecodes
from datetime import datetime, timedelta
from four_button_pages import StaticMenu, TokenEntryMenu, PAYGStatusMenu


class FourButtonUserInterface(object):

    BACKLIGHT_TIMEOUT = 300

    def __init__(self, lcd, conn, kbd, static_pages):
        self.conn = conn
        self.disp = lcd
        self.kbd = kbd
        self.static_pages = static_pages
        self.last_key_pressed = datetime.now()
        self.selected_menu = None
        self.current_menu = None
        self.index = 0
        self.last_index = 1
        self.menus = [
            ('PAYG Status', PAYGStatusMenu(self.conn)),
            ('Enter Token', TokenEntryMenu(self.conn)),
            ('LAN Status', StaticMenu(self.static_pages[16])),
            ('WiFi Status', StaticMenu(self.static_pages[17])),
            ('General Status', StaticMenu(self.static_pages[0])),
            ('Solar Status', StaticMenu(self.static_pages[12])),
            ('Battery Status', StaticMenu(self.static_pages[11])),
            ('Solar History', StaticMenu(self.static_pages[14])),
        ]
        self.alarm_menus = [
            StaticMenu(self.static_pages[2]), # VE Bus error
            StaticMenu(self.static_pages[3]),  # VE Bus alarm
            StaticMenu(self.static_pages[13]),  # Solar error
        ]

    def start(self):
        self.disp.clear()
        self.update_menu_list()

    def key_pressed(self):
        self.last_key_pressed = datetime.now()
        for event in self.kbd.read():
            if event.type == ecodes.EV_KEY and event.value == 1:
                self.update_current_menu(event.code)

    def tick(self):
        self.display_alarms()
        self.update_current_menu(None)
        self.update_backlight_status()

    def update_backlight_status(self):
        if self.last_key_pressed + timedelta(seconds=self.BACKLIGHT_TIMEOUT) < datetime.now():
            self.disp.on = False
        else:
            self.disp.on = True

    def display_alarms(self):
        for alarm in self.alarm_menus:
            alarm.enter(self.conn, self.disp) # It will only display if the menu actually exists

    def get_available_menus(self):
        menus = []
        for menu in self.menus:
            if menu[1].is_available(self.conn):
                menus.append(menu)
        return menus

    def update_menu_list(self):
        menus = self.get_available_menus()

        if self.index < self.last_index:
            top_string = menus[self.index][0].ljust(15, ' ') + '>'
            bottom_string = menus[self.index + 1][0].ljust(15, ' ') + ' '
        else:
            top_string = menus[self.index - 1][0].ljust(15, ' ') + ' '
            bottom_string = menus[self.index][0].ljust(15, ' ') + '>'

        self.disp.display_string(top_string, 1)
        self.disp.display_string(bottom_string, 2)

        self.selected_menu = menus[self.index][1]

    def menu_list_loop(self, key_pressed):
        number_of_menus = len(self.get_available_menus())
        if key_pressed == ecodes.KEY_UP:
            if self.index > 0:
                self.last_index = self.index
                self.index -= 1
                self.update_menu_list()
        if key_pressed == ecodes.KEY_DOWN:
            if self.index < number_of_menus - 1:
                self.last_index = self.index
                self.index += 1
                self.update_menu_list()
        if key_pressed == ecodes.KEY_RIGHT:
            self.current_menu = self.selected_menu
            self.current_menu.enter(self.conn, self.disp)

    def update_current_menu(self, key_pressed):
        if self.current_menu is not None and not self.current_menu.update(self.conn, self.disp, key_pressed):
            self.current_menu = None
            key_pressed = None
            self.disp.clear()
            self.update_menu_list()
        if self.current_menu is None:
            self.menu_list_loop(key_pressed)
