from sqlalchemy import DateTime, MetaData, Table, Column, Integer, ForeignKey, BOOLEAN, Text
from database.electionStatus import ElectionStatus
from database.base import Base
from datetime import datetime


class KnownUser(Base):
    __tablename__ = 'knownUsers'
    """Class for storing known users"""
    knownUserID = Column(Integer, primary_key=True, autoincrement=True)
    botName = Column(Text)
    userID = Column(Text)
    isKnown = Column(BOOLEAN)

    def __init__(self, botName: str, userID: str, isKnown: bool = True, knownUserID: int = None):
        """Initialization object"""
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(userID, str), "userID is not a string"
        assert isinstance(isKnown, bool), "isKnown is not a boolean"
        assert isinstance(knownUserID, (bool, type(None))), "knownUserID is not an bool or None"

        self.knownUserID = knownUserID
        self.botName = botName
        self.userID = userID
        self.isKnown = isKnown

    def __str__(self):
        return "knownUserID: " + str(self.knownUserID) + \
               ", botName: " + str(self.botName) +\
               ", userID: " + str(self.userIDs) +\
               ", isKnown: " + str(self.isKnown)

