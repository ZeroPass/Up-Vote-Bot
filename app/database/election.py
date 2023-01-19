from sqlalchemy import DateTime, MetaData, Table, Column, Integer, ForeignKey, BOOLEAN
from database.electionStatus import ElectionStatus
from database.base import Base
from datetime import datetime


class Election(Base):
    __tablename__ = 'election'
    """Class for interaction between code structure and database"""
    electionID = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime)
    status = Column(Integer, ForeignKey(ElectionStatus.electionStatusID))

    def __init__(self, date: datetime, status: ElectionStatus,  electionID: int = None):
        """Initialization object"""
        assert isinstance(date, datetime), "date must be type of datetime"
        assert isinstance(status, ElectionStatus), "status must be type of ElectionStatus"

        self.electionID = electionID
        self.date = date
        self.status = status.electionStatusID

    def __str__(self):
        return "ElectionID: " + str(self.electionID) + \
               " Date: " + str(self.date.strftime("%d.%m.%Y %H:%M:%S")) +\
               " Status: " + str(self.status)
