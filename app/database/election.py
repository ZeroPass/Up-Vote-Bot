from sqlalchemy import DateTime, MetaData, Table, Column, Integer, ForeignKey
from app.database.electionStatus import ElectionStatus
from app.database.base import Base
from datetime import datetime

class Election(Base):
    __tablename__ = 'election'
    """Class for interaction between code structure and database"""
    electionID = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime)
    status = Column(Integer, ForeignKey(ElectionStatus.electionStatusID))


    def __init__(self, date: datetime, status: ElectionStatus, electionID: int = None):
        """Initialization object"""
        assert isinstance(date, datetime)
        assert isinstance(status, ElectionStatus)

        self.electionID = electionID
        self.date = date
        self.status = status.electionStatusID