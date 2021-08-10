from datetime import datetime, timedelta
from track import Tracker


class PAYGService(object):
    SERVICE_NAME = 'com.victronenergy.paygo'

    def __init__(self, conn):
        self.conn = conn
        self.tracker = Tracker()

    def service_available(self):
        payg_enabled = self.tracker.query(self.conn, self.SERVICE_NAME, "/Status/PaygoEnabled")
        if payg_enabled is None:
            return False
        else:
            return True

    def is_active(self):
        is_active = self.tracker.query(self.conn, self.SERVICE_NAME, "/Status/CurrentlyActive")
        if is_active:
            return True
        else:
            return False

    def is_payg_enabled(self):
        payg_enabled = self.tracker.query(self.conn, self.SERVICE_NAME, "/Status/PaygoEnabled")
        if payg_enabled is not None:
            return payg_enabled
        else:
            return True

    def token_entry_allowed(self):
        if not self._get_blocked_until_date():
            return True
        if datetime.now() >= self._get_blocked_until_date():
            return True
        else:
            return False

    def get_minutes_of_token_block(self):
        if not self._get_blocked_until_date():
            return 0
        td = self._get_blocked_until_date() - datetime.now()
        days_left = td.days
        minutes_left = int(round(float(td.seconds) / 60, 0))
        return minutes_left+(days_left*60*24)

    def get_number_of_days_and_hours_left(self):
        if not self._get_expiration_date():
            return 0, 0
        td = self._get_expiration_date() - datetime.now()
        days_left = td.days
        hours_left = int(round(float(td.seconds)/3600, 0))
        if hours_left == 24:
            days_left += 1
            hours_left = 0
        return days_left, hours_left

    def update_device_status_if_code_valid(self, token):
        self._dbus_write(self.SERVICE_NAME, "/Tokens/Last", token)
        token_valid = self.tracker.query(self.conn, self.SERVICE_NAME, "/Tokens/LastTokenValid")
        return token_valid

    def update_lvd_value(self, new_lvd_volts):
        self._dbus_write(self.SERVICE_NAME, "/LVD/Threshold", new_lvd_volts)
        return True

    def get_lvd_value(self):
        lvd_value = self.tracker.query(self.conn, self.SERVICE_NAME, "/LVD/Threshold")
        if lvd_value is not None:
            return lvd_value
        return None

    def _get_expiration_date(self):
        expiration_date = self.tracker.query(self.conn, self.SERVICE_NAME, "/Status/ActiveUntilDate")
        if expiration_date is not None:
            return self._datetime_from_unix_timestamp(expiration_date)
        return None

    def _get_blocked_until_date(self):
        blocked_until_date = self.tracker.query(self.conn, self.SERVICE_NAME, "/Tokens/EntryBlockedUntilDate")
        if blocked_until_date is not None:
            return self._datetime_from_unix_timestamp(blocked_until_date)
        return None

    def _dbus_write(self, service_name, path, value):
        return self.conn.call_blocking(service_name, path, None, "SetValue", 's', [str(value)])

    def _datetime_from_unix_timestamp(self, timestamp):
        return datetime(1970, 1, 1) + timedelta(seconds=timestamp)
