from enum import Enum

class ReminderGroup(Enum):
    """Enum for reminder group"""
    NOT_ATTENDED = 0
    ATTENDED = 1
    BOTH = 2