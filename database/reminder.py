from enum import Enum
from datetime import datetime
from sqlalchemy import DateTime, Column, Integer, ForeignKey, CHAR

from constants import ReminderGroup
from database.participant import Participant
from database.election import Election
from database.base import Base


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
    round = Column(Integer, nullable=True)  # going to be used only for time's up reminder
    reminderGroup = Column(Integer)

    def __init__(self, dateTimeBefore: datetime, electionID: int, reminderGroup: ReminderGroup = ReminderGroup.BOTH,
                 round: int = None, reminderID: int = None):
        """Initialization object"""
        assert isinstance(electionID, int), "ElectionID must be int"
        assert isinstance(dateTimeBefore, datetime), "DateTimeBefore must be datetime"
        assert isinstance(round, (int, type(None))), "Round must be int or None"
        assert isinstance(reminderGroup, ReminderGroup), "ReminderGroup must be ReminderGroup"
        assert isinstance(reminderID, (int, type(None))), "ReminderID must be int or None"

        self.reminderID = reminderID
        self.dateTimeBefore = dateTimeBefore
        self.round = round
        self.reminderGroup = reminderGroup.value
        self.electionID = electionID

    def __str__(self):
        return "ReminderID: " + str(self.reminderID) if self.reminderID is not None else "<None>" + \
               " DateTimeBefore: " + str(self.dateTimeBefore) + \
               " ElectionID: " + str(self.electionID) + \
               " Round: " + str(self.round) + \
               " ReminderGroup: " + str(self.reminderGroup)


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
