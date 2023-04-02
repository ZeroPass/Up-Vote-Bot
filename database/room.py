from datetime import datetime
from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text, CHAR, BOOLEAN, DateTime
from database.election import Election
from database.base import Base

ROOM_PREDISPOSED_BY_PROCESS = "process"
class Room(Base):
    __tablename__ = 'room'
    """Class for interaction between code structure and database"""
    roomID = Column(Integer, primary_key=True, autoincrement=True)
    electionID = Column(Integer, ForeignKey(Election.electionID), nullable=False)
    roomNameShort = Column(CHAR(128), nullable=False)
    roomNameLong = Column(CHAR(128), nullable=False)
    isPredisposed = Column(BOOLEAN, nullable=False)
    predisposedBy = Column(CHAR(128), nullable=False)
    predisposedDateTime = Column(DateTime)
    round = Column(Integer, nullable=False)
    roomIndex = Column(Integer, nullable=False)
    roomTelegramID = Column(CHAR(128))
    shareLink = Column(CHAR(128))
    isArchived = Column(BOOLEAN, nullable=False)

    def __init__(self,
                 electionID: int,
                 round: int,
                 roomIndex: int,
                 roomNameShort: str,
                 roomNameLong: str,
                 isPredisposed: bool = False,
                 predisposedBy: str = ROOM_PREDISPOSED_BY_PROCESS,
                 predisposedDateTime: datetime = None,
                 roomID: int = None,
                 roomTelegramID: str = None,
                 shareLink: str = None,
                 isArchived: bool = False
                 ):
        """Initialization object"""
        assert isinstance(roomID, (int, type(None))), "roomID is not an integer or None"
        assert isinstance(electionID, int), "electionID is not an integer"
        assert isinstance(roomNameShort, str), "roomNameShort is not a string"
        assert isinstance(roomNameLong, str), "roomNameLong is not a string"
        assert isinstance(isPredisposed, bool), "isPredisposed is not a boolean"
        assert isinstance(predisposedBy, str), "predisposedBy is not a string"
        assert isinstance(round, int), "round is not an integer"
        assert isinstance(roomIndex, int), "roomIndex is not an integer"
        assert isinstance(predisposedDateTime, (datetime, type(None))), "predisposedDateTime is not a datetime or None"
        assert isinstance(roomTelegramID, (str, type(None))), "roomTelegramID is not a string or None"
        assert isinstance(shareLink, (str, type(None))), "shareLink is not a string or None"
        assert isinstance(isArchived, bool), "isArchived is not a boolean"

        self.roomID = roomID
        self.electionID = electionID
        self.roomNameShort = roomNameShort
        self.roomNameLong = roomNameLong
        self.isPredisposed = isPredisposed
        self.predisposedBy = predisposedBy
        self.round = round
        self.roomIndex = roomIndex
        self.predisposedDateTime = predisposedDateTime
        self.roomTelegramID = roomTelegramID
        self.shareLink = shareLink
        self.isArchived = isArchived
