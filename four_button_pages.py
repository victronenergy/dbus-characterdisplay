from evdev import ecodes
from payg_service import PAYGService


class StaticMenu(object):

    def __init__(self, static_page):
        self._static_page = static_page

    def is_available(self, conn):
        if self._static_page.get_text(conn) is None:
            return False
        return True

    def enter(self, conn, display):
        self._static_page.display(conn, display)

    def update(self, conn, display, key_pressed):
        if key_pressed:
            return False
        return True


class TokenEntryMenu(object):

    def __init__(self, conn):
        self.conn = conn
        self.payg_service = PAYGService(self.conn)
        self.number_entry_menu = NumberEntryMenu(conn, 9, 'Enter Token', self.complete_token_entry)

    def is_available(self, conn):
        return self.payg_service.service_available()

    def enter(self, conn, display):
        self.was_locked = False

        display.clear()

        if not self.payg_service.token_entry_allowed():
            display.display_string('Token entry lock'.center(16), 1)
            minutes = self.payg_service.get_minutes_of_token_block()
            date_string = 'for {minutes} min.'.format(minutes=minutes)
            display.display_string(date_string.center(16), 2)
        else:
            self.number_entry_menu.enter(conn, display)


    def update(self, conn, display, key_pressed):
        if not self.payg_service.token_entry_allowed():
            display.display_string('Token entry lock'.center(16), 1)
            minutes = self.payg_service.get_minutes_of_token_block()
            date_string = 'for {minutes} min.'.format(minutes=minutes)
            display.display_string(date_string.center(16), 2)
            self.was_locked = True
            if key_pressed == ecodes.KEY_LEFT:
                return False
        else:
            if self.was_locked:
                display.clear()
                self.was_locked = False
                self.number_entry_menu.enter(conn, display)
            return self.number_entry_menu.update(conn, display, key_pressed)
        return True

    def complete_token_entry(self, conn, display, token_typed):
        token_status = self.payg_service.update_device_status_if_code_valid(int(token_typed))
        display.clear()
        if token_status == 1:
            display.display_string('Token Valid'.center(16), 1)
            if not self.payg_service.is_payg_enabled():
                display.display_string('Active Forever'.center(16), 2)
            else:
                days_left, hours_left = self.payg_service.get_number_of_days_and_hours_left()
                date_string = '{days} days, {hours} h'.format(days=days_left, hours=hours_left)
                display.display_string(date_string.center(16), 2)
        elif token_status == -2:
            display.display_string('Token'.center(16), 1)
            display.display_string('Already Used'.center(16), 2)
        else:
            display.display_string('Token Invalid'.center(16), 1)
            display.display_string(''.center(16), 2)


class PAYGStatusMenu(object):

    def __init__(self, conn):
        self.conn = conn
        self.payg_service = PAYGService(self.conn)

    def is_available(self, conn):
        return self.payg_service.service_available()

    def enter(self, conn, display):
        if not self.payg_service.is_payg_enabled():
            display.display_string('Active'.center(16), 1)
            display.display_string('Forever'.center(16), 2)
        elif self.payg_service.is_active():
            display.display_string('Active For'.center(16), 1)
            days_left, hours_left = self.payg_service.get_number_of_days_and_hours_left()
            date_string = '{days} days, {hours} h'.format(days=days_left, hours=hours_left)
            display.display_string(date_string.center(16), 2)
        else:
            display.display_string('Not Active'.center(16), 1)
            display.display_string('Please Activate'.center(16), 2)

    def update(self, conn, display, key_pressed):
        if key_pressed:
            return False
        return True


class NumberEntryMenu(object):

    def __init__(self, conn, number_length, prompt_text, callback_function, starting_value_callback=None):
        self.conn = conn
        self.number_length = number_length
        self.prompt_text = prompt_text
        self.callback_function = callback_function
        self.starting_value_callback = starting_value_callback
        self.ready = False

    def is_available(self, conn):
        return False

    def enter(self, conn, display):
        if not self.starting_value_callback:
            self.number_typed = ''
            self.current_digit = 5
        else:
            starting_value = self.starting_value_callback()
            self.number_typed = starting_value[:-1]
            self.current_digit = int(starting_value[-1])
        self.entry_complete = False
        self.to_display = self.number_typed + str(self.current_digit)

        display.clear()
        display.display_string(self.prompt_text, 1)
        display.display_string(self.to_display.ljust(self.number_length, '_'), 2)
        self.ready = True

    def update(self, conn, display, key_pressed):
        if not self.ready:
            return True
        if self.entry_complete:
            if key_pressed:
                return False
            return True
        if key_pressed == ecodes.KEY_RIGHT:
            self.number_typed = self.number_typed + str(self.current_digit)
            if len(self.number_typed) == self.number_length:
                self.entry_complete = True
                self.callback_function(conn, display, self.number_typed)
                return True
            self.current_digit = 5
        if key_pressed == ecodes.KEY_LEFT:
            if len(self.number_typed) == 0:
                return False
            else:
                self.current_digit = int(self.number_typed[-1:]) if self.number_typed[-1:] else 5
                self.number_typed = self.number_typed[:-1]
        if key_pressed == ecodes.KEY_UP:
            self.current_digit += 1
            if self.current_digit > 9:
                self.current_digit = 0
        if key_pressed == ecodes.KEY_DOWN:
            self.current_digit -= 1
            if self.current_digit < 0:
                self.current_digit = 9
        if key_pressed:
            self.to_display = self.number_typed + str(self.current_digit)
            display.display_string(self.prompt_text, 1)
            display.display_string(self.to_display.ljust(self.number_length, '_'), 2)
        return True


class ServiceMenu(object):

    def __init__(self, conn):
        self.conn = conn
        self.payg_service = PAYGService(self.conn)
        self.password_entry_menu = NumberEntryMenu(conn, 6, 'Service Password', self.validate_password)
        self.lvd_entry_menu = NumberEntryMenu(conn, 5, 'LVD Thres. (mV):', self.save_lvd, starting_value_callback=self.get_lvd_string)

    def is_available(self, conn):
        return self.payg_service.service_available()

    def enter(self, conn, display):
        self.password_valid = None
        self.lvd_set = None
        self.password_entry_menu.enter(conn, display)

    def update(self, conn, display, key_pressed):
        if self.password_valid is None:
            return self.password_entry_menu.update(conn, display, key_pressed)
        elif self.password_valid == True:
            if not self.lvd_set:
                return self.lvd_entry_menu.update(conn, display, key_pressed)
            else:
                if key_pressed:
                    return False
        else:
            if key_pressed:
                return False
        return True

    def validate_password(self, conn, display, password):
        if password == '567415':
            self.password_valid = True
            self.lvd_entry_menu.enter(conn, display)
        else:
            display.clear()
            display.display_string('Wrong password!', 1)
            display.display_string('Try again', 2)
            self.password_valid = False
        return True

    def save_lvd(self, conn, display, new_lvd):
        new_lvd_volts = int(new_lvd)/1000.0
        self.payg_service.update_lvd_value(new_lvd_volts)
        display.clear()
        display.display_string('New LVD: ', 1)
        display.display_string('{new_lvd_volts} V'.format(new_lvd_volts=new_lvd_volts), 2)
        self.lvd_set = True
        return True

    def get_lvd_string(self):
        lvd_value = self.payg_service.get_lvd_value()
        if not lvd_value:
            lvd_value = 11.5
        lvd_value_string = str(int(float(lvd_value)*1000))
        return lvd_value_string
