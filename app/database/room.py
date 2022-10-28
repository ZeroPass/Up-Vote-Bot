from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text, CHAR
from app.database.election import Election
from app.database.base import Base


class Room(Base):
    __tablename__ = 'room'
    """Class for interaction between code structure and database"""
    roomID = Column(Integer, primary_key=True, autoincrement=True)
    electionID = Column(Integer, ForeignKey(Election.electionID), nullable=False)
    roomNameShort = Column(CHAR(128), nullable=False)
    roomNameLong = Column(CHAR(128), nullable=False)
    round = Column(Integer, nullable=False)
    roomIndex = Column(Integer, nullable=False)
    roomTelegramID = Column(Integer, nullable=True)

    def __init__(self, electionID: int, round: int, roomIndex: int, roomNameShort: str, roomNameLong: str,
                 roomID: int = None, roomTelegramID: int = None):
        """Initialization object"""
        assert isinstance(roomID, (int, type(None)))
        assert isinstance(electionID, int)
        assert isinstance(roomNameShort, str)
        assert isinstance(roomNameLong, str)
        assert isinstance(round, int)
        assert isinstance(roomIndex, int)
        assert isinstance(roomTelegramID, (int, type(None)))

        self.roomID = roomID
        self.electionID = electionID
        self.roomNameShort = roomNameShort
        self.roomNameLong = roomNameLong
        self.round = round
        self.roomIndex = roomIndex
        self.roomTelegramID = roomTelegramID
