from typing import Tuple
import logging

class TimeManager:
    """Manage wait time formats and enforce wait time limits."""

    # Constants for time values
    SECONDS_IN_MINUTE = 60
    SECONDS_IN_HOUR = 3600
    MAX_WAIT_TIME = 43200  # 12 hours in seconds

    @staticmethod
    def format_wait_time(wait_time: int) -> Tuple[int, str]:
        """Format the wait time into a human-readable form."""
        if wait_time < TimeManager.SECONDS_IN_MINUTE:
            return wait_time, 'seconds'
        elif wait_time < TimeManager.SECONDS_IN_HOUR:
            return wait_time / TimeManager.SECONDS_IN_MINUTE, 'minutes'
        else:
            return wait_time / TimeManager.SECONDS_IN_HOUR, 'hours'

    @staticmethod
    def enforce_max_wait_time(wait_time: int) -> int:
        """Enforce a maximum wait time limit."""
        if wait_time > TimeManager.MAX_WAIT_TIME:
            logging.warning("Wait time exceeded limit of 12 hours, setting to default 1 hours.")
            return TimeManager.SECONDS_IN_HOUR
        return wait_time
