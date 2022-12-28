from datetime import datetime
from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text, CHAR, BOOLEAN, DateTime
from app.database.election import Election
from app.database.base import Base


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

    def __init__(self,
                 electionID: int,
                 round: int,
                 roomIndex: int,
                 roomNameShort: str,
                 roomNameLong: str,
                 isPredisposed: bool = False,
                 predisposedBy: str = "process",
                 predisposedDateTime: datetime = None,
                 roomID: int = None,
                 roomTelegramID: str = None,
                 shareLink: str = None
                 ):
        """Initialization object"""
        assert isinstance(roomID, (int, type(None)))
        assert isinstance(electionID, int)
        assert isinstance(roomNameShort, str)
        assert isinstance(roomNameLong, str)
        assert isinstance(isPredisposed, bool)
        assert isinstance(predisposedBy, str)
        assert isinstance(round, int)
        assert isinstance(roomIndex, int)
        assert isinstance(predisposedDateTime, (datetime, type(None)))
        assert isinstance(roomTelegramID, (str, type(None)))
        assert isinstance(shareLink, (str, type(None)))

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
