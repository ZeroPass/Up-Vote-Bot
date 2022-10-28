from typing import Optional

from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text

from app.constants import CurrentElectionState
from app.database.base import Base

"""
class StatusType():
    def __init__(self, status: str, description: Optional[str] = None):
        self.status = status
        self.description = description"""


class ElectionStatus(Base):
    __tablename__ = 'electionStatus'
    """Class for interaction between code structure and database"""
    electionStatusID = Column(Integer, primary_key=True, autoincrement=False) #should not be autoincremented
    status = Column(Text, nullable=False)
    description = Column(Text)

    def __init__(self, electionStatusID: int, status: CurrentElectionState, description: Optional[Text] = None):
        """Initialization object"""
        assert isinstance(electionStatusID, int)
        assert isinstance(status, CurrentElectionState)
        assert isinstance(description, (String, type(None)))

        self.electionStatusID = electionStatusID
        self.status = status.value
        self.description = description

