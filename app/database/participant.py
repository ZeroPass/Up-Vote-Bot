from app.database.room import Room
from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text, CHAR, BOOLEAN
from app.database.base import Base


class Participant(Base):
    __tablename__ = 'participant'
    """Class for interaction between code structure and database"""
    accountName = Column(CHAR(32), primary_key=True)
    roomID = Column(Integer, ForeignKey(Room.roomID), nullable=False)
    participationStatus = Column(BOOLEAN)
    telegramID = Column(Text)
    nftTemplateID = Column(Integer)
    participantName = Column(Text)

    """@staticmethod
    def createTable(meta):
        return Table(
            'participant', meta,
            Column('participantID', Integer, primary_key=True, autoincrement=True),
            Column('roomID', CHAR(100), ForeignKey('room.roomID'), nullable=False),
            Column('telegramID', Text),
            Column('participantName', Text)
        )"""

    def __init__(self, accountName: str, roomID: int, participationStatus: bool, telegramID: str, nftTemplateID: int,
                 participantName: str):
        """Initialization object"""
        assert isinstance(accountName, str)
        assert isinstance(roomID, (int, type(None)))
        assert isinstance(participationStatus, bool)
        assert isinstance(telegramID, str)
        assert isinstance(nftTemplateID, int)
        assert isinstance(participantName, str)

        self.accountName = accountName
        self.roomID = roomID
        self.participationStatus = participationStatus
        self.telegramID = telegramID
        self.nftTemplateID = nftTemplateID
        self.participantName = participantName

    def __eq__(self, other):
        if not isinstance(other, Participant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.accountName == other.accountName and \
               self.roomID == other.roomID and \
               self.participationStatus == other.participationStatus and \
               self.telegramID == other.telegramID and \
               self.nftTemplateID == other.nftTemplateID and \
               self.participantName == other.participantName


