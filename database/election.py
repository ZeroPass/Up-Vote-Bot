import enum

from sqlalchemy import DateTime, MetaData, Table, Column, Integer, ForeignKey, BOOLEAN, Text
from database.electionStatus import ElectionStatus
from database.base import Base
from datetime import datetime


class ElectionRound(enum.Enum):
    DEFAULT: int = -1
    NOT_DEFINED: int = 505
    FINAL: int = 99

class Election(Base):
    __tablename__ = 'election'
    """Class for interaction between code structure and database"""
    electionID = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime)
    status = Column(Integer, ForeignKey(ElectionStatus.electionStatusID))
    contract = Column(Text)
    roundLive = Column(Integer, default=-1)

    def __init__(self, date: datetime, status: ElectionStatus, contract: str,
                 roundLive: int = ElectionRound.NOT_DEFINED.value, electionID: int = None):
        """Initialization object"""
        assert isinstance(date, datetime), "date must be type of datetime"
        assert isinstance(status, ElectionStatus), "status must be type of ElectionStatus"
        assert isinstance(contract, str), "contract must be type of str"
        assert isinstance(roundLive, int), "roundLive must be type of int"

        self.electionID = electionID
        self.date = date
        self.status = status.electionStatusID
        self.contract = contract
        self.roundLive = roundLive

    def __str__(self):
        return "ElectionID: " + str(self.electionID) + \
               ", Date: " + str(self.date.strftime("%d.%m.%Y %H:%M:%S")) +\
               ", Status: " + str(self.status) +\
               ", Contract: " + str(self.contract) +\
               ", RoundLive: " + str(self.roundLive)

    @classmethod
    def copy(self, election, status: ElectionStatus):
        return Election(date=election.date,
                        status=status,
                        contract=election.contract,
                        electionID=election.electionID,
                        roundLive=election.roundLive
                        )