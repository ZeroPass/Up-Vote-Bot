from enum import Enum
from typing import Optional
from datetime import datetime
from sqlalchemy import DateTime, Column, Integer, ForeignKey, Text, CHAR

from app.constants import ReminderGroup
from app.database.participant import Participant
from app.database.election import Election
from app.database.base import Base


class ReminderSendStatus(Enum):
    """Enum for reminder send status"""
    FAILED = None
    NOT_SEND = 0
    SEND = 1
    ERROR = 2

class Reminder(Base):
    __tablename__ = 'reminder'
    """Class for interaction between code structure and database"""
    reminderID = Column(Integer, primary_key=True, autoincrement=True)
    dateTimeBefore = Column(DateTime)
    electionID = Column(Integer, ForeignKey(Election.electionID))
    reminderGroup = Column(Integer)

    def __init__(self, dateTimeBefore: datetime, electionID: int, reminderGroup: ReminderGroup = ReminderGroup.BOTH, reminderID: int = None):
        """Initialization object"""
        assert isinstance(electionID, int)
        assert isinstance(dateTimeBefore, datetime)
        assert isinstance(reminderGroup, ReminderGroup)
        assert isinstance(reminderID, (int, type(None)))

        self.reminderID = reminderID
        self.dateTimeBefore = dateTimeBefore
        self.reminderGroup = reminderGroup.value
        self.electionID = electionID


class ReminderSent(Base):
    __tablename__ = 'reminderSent'
    """Class for interaction between code structure and database"""
    reminderSentID = Column(Integer, primary_key=True, autoincrement=True)
    reminderID = Column(Integer, ForeignKey(Reminder.reminderID))
    accountName = Column(CHAR(32), ForeignKey(Participant.accountName))
    sendStatus = Column(Integer)  # 0 - not sent, 1 - sent, 2 - error

    def __init__(self, reminderID: int, accountName: str, sendStatus: ReminderSendStatus, reminderSentID: Reminder = None):
        """Initialization object"""
        assert isinstance(reminderSentID, (int, type(None)))
        assert isinstance(reminderID, int)
        assert isinstance(accountName, str)
        assert isinstance(sendStatus, Enum)

        self.reminderSentID = reminderSentID
        self.reminderID = reminderID
        self.accountName = accountName
        self.sendStatus = sendStatus.value
