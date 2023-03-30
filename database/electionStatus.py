from typing import Optional

from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text, BOOLEAN

from constants import CurrentElectionState
from database.base import Base


class ElectionStatus(Base):
    __tablename__ = 'electionStatus'
    """Class for interaction between code structure and database"""
    electionStatusID = Column(Integer, primary_key=True, autoincrement=False) #should not be autoincremented
    status = Column(Text, nullable=False)
    isLive = Column(BOOLEAN, default=False)
    description = Column(Text)

    def __init__(self, electionStatusID: int, status: CurrentElectionState, isLive: bool = False,
                 description: Optional[Text] = None):
        """Initialization object"""
        assert isinstance(electionStatusID, int), "electionStatusID must be type of int"
        assert isinstance(status, CurrentElectionState), "status must be type of CurrentElectionState"
        assert isinstance(description, (String, type(None))), "description must be type of str or None"
        assert isinstance(isLive, bool), "isLive must be type of bool"

        self.electionStatusID = electionStatusID
        self.status = status.value
        self.description = description
        self.isLive = isLive

