from evdev import ecodes
from datetime import datetime, timedelta
from four_button_pages import StaticMenu, TokenEntryMenu, PAYGStatusMenu
from pages import BatteryPage, SolarPage, LanPage, WlanPage
from pages import InverterInfoPage, PVInfoPage, NotificationsPage

class FourButtonUserInterface(object):

    BACKLIGHT_TIMEOUT = 300

    def __init__(self, lcd, conn, kbd, static_pages):
        self.conn = conn
        self.disp = self.lcd = lcd
        self.kbd = kbd
        self.static_pages = static_pages
        self.last_key_pressed = datetime.now()
        self.selected_menu = None
        self.current_menu = None
        self.index = 0
        self.last_index = 1
        self.last_menu_number = 0
        self.menus = [
            (_('PAYG Status'), PAYGStatusMenu(self.conn)),
            (_('Enter Token'), TokenEntryMenu(self.conn)),
            (_('LAN Status'), StaticMenu(self, LanPage.instance)),
            (_('WiFi Status'), StaticMenu(self, WlanPage.instance)),
            (_('General Status'), StaticMenu(self, InverterInfoPage.instance)),
            (_('Solar Status'), StaticMenu(self, PVInfoPage.instance)),
            (_('Battery Status'), StaticMenu(self, BatteryPage.instance)),
            (_('Solar History'), StaticMenu(self, SolarPage.instance)),
        ]
        self.notificationmenu = StaticMenu(self, NotificationsPage.instance)

    def start(self):
        self.disp.clear()
        self.update_menu_list()

    def key_pressed(self):
        self.last_key_pressed = datetime.now()
        for event in self.kbd.read():
            if event.type == ecodes.EV_KEY and event.value == 1:
                self.update_current_menu(event.code)

    def tick(self):
        if not self.display_alarms():
            self.update_current_menu(None)
            self.update_backlight_status()

    def update_backlight_status(self):
        if self.last_key_pressed + timedelta(seconds=self.BACKLIGHT_TIMEOUT) < datetime.now():
            self.disp.on = False
        else:
            self.disp.on = True

    def display_alarms(self):
        if self.notificationmenu.urgent:
            self.current_menu = self.notificationmenu
            self.current_menu.enter(self.conn, self.disp)
            return True
        return False

    def get_available_menus(self):
        menus = []
        for menu in self.menus:
            if menu[1].is_available(self.conn):
                menus.append(menu)
        return menus

    def update_menu_list(self):
        menus = self.get_available_menus()

        number_menus = len(menus)
        if number_menus < self.last_menu_number:
            self.index = 0
        self.last_menu_number = number_menus

        if number_menus == 0:
            top_string = ' Victron Energy '
            bottom_string = ' '.ljust(16, ' ')
        elif number_menus == 1:
            top_string = menus[0][0].ljust(15, ' ') + '>'
            bottom_string = ' '.ljust(16, ' ')
        else:
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
        else:
            self.update_menu_list()

    def update_current_menu(self, key_pressed):
        if self.current_menu is not None and not self.current_menu.update(self.conn, self.disp, key_pressed):
            self.current_menu = None
            key_pressed = None
            self.disp.clear()
            self.update_menu_list()
        if self.current_menu is None:
            self.menu_list_loop(key_pressed)
