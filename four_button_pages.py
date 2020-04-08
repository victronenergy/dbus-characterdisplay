from evdev import ecodes
from payg_service import PAYGService


class StaticMenu(object):

    def __init__(self, ui, static_page):
        self.ui = ui
        self._static_page = static_page

    def is_available(self, conn):
        if self._static_page.get_text(conn) is None:
            return False
        return True

    def enter(self, conn, display):
        self._static_page.display(conn, display)

    def update(self, conn, display, key_pressed):
        if key_pressed:
            return self._static_page.key_pressed(self.ui, key_pressed)
        return True

    @property
    def urgent(self):
        return self._static_page.urgent


class TokenEntryMenu(object):

    def __init__(self, conn):
        self.conn = conn
        self.payg_service = PAYGService(self.conn)

    def is_available(self, conn):
        return self.payg_service.service_available()

    def enter(self, conn, display):
        self.was_locked = False
        self.token_typed = ''
        self.current_digit = 5
        self.token_entry_complete = False
        self.to_display = self.token_typed + str(self.current_digit)

        display.clear()

        if not self.payg_service.token_entry_allowed():
            display.display_string('Token entry lock'.center(16), 1)
            minutes = self.payg_service.get_minutes_of_token_block()
            date_string = 'for {minutes} min.'.format(minutes=minutes)
            display.display_string(date_string.center(16), 2)
        else:
            display.display_string('Enter Token', 1)
            display.display_string(self.to_display.ljust(9, '_'), 2)

    def update(self, conn, display, key_pressed):
        if self.token_entry_complete:
            if key_pressed:
                return False
            return True
        if not self.payg_service.token_entry_allowed():
            display.display_string('Token entry lock'.center(16), 1)
            minutes = self.payg_service.get_minutes_of_token_block()
            date_string = 'for {minutes} min.'.format(minutes=minutes)
            display.display_string(date_string.center(16), 2)
            self.was_locked = True
            if key_pressed == ecodes.KEY_LEFT:
                return False
        else:
            if key_pressed == ecodes.KEY_RIGHT:
                self.token_typed = self.token_typed + str(self.current_digit)
                if len(self.token_typed) == 9:
                    self.complete_token_entry(display, self.token_typed)
                    return True
                self.current_digit = 5
            if key_pressed == ecodes.KEY_LEFT:
                if len(self.token_typed) == 0:
                    return False
                else:
                    self.current_digit = int(self.token_typed[-1:]) if self.token_typed[-1:] else 5
                    self.token_typed = self.token_typed[:-1]
            if key_pressed == ecodes.KEY_UP:
                self.current_digit += 1
                if self.current_digit > 9:
                    self.current_digit = 0
            if key_pressed == ecodes.KEY_DOWN:
                self.current_digit -= 1
                if self.current_digit < 0:
                    self.current_digit = 9
            if key_pressed or self.was_locked:
                if self.was_locked:
                    display.clear()
                    self.was_locked = False
                self.to_display = self.token_typed + str(self.current_digit)
                display.display_string('Enter Token', 1)
                display.display_string(self.to_display.ljust(9, '_'), 2)
        return True

    def complete_token_entry(self, display, token_typed):
        self.token_entry_complete = True
        is_token_valid = self.payg_service.update_device_status_if_code_valid(int(token_typed))
        display.clear()
        if is_token_valid:
            display.display_string('Token Valid'.center(16), 1)
            if not self.payg_service.is_payg_enabled():
                display.display_string('Active Forever'.center(16), 2)
            else:
                days_left, hours_left = self.payg_service.get_number_of_days_and_hours_left()
                date_string = '{days} days, {hours} h'.format(days=days_left, hours=hours_left)
                display.display_string(date_string.center(16), 2)
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
