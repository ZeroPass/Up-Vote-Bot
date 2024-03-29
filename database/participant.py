from database.room import Room
from sqlalchemy import String, Table, Column, Integer, ForeignKey, Text, CHAR, BOOLEAN
from database.base import Base


class Participant(Base):
    __tablename__ = 'participant'
    """Class for interaction between code structure and database"""
    accountName = Column(CHAR(32), primary_key=True)
    roomID = Column(Integer, ForeignKey(Room.roomID), nullable=False, primary_key=True)
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

    @classmethod
    def deepCopy(cls, participant):
        assert isinstance(participant, Participant), "participant must be type of Participant"
        return cls(accountName=participant.accountName,
                   roomID=participant.roomID,
                   participationStatus=participant.participationStatus,
                   telegramID=participant.telegramID,
                   nftTemplateID=participant.nftTemplateID,
                   participantName=participant.participantName)

    def __str__(self):
        return f"Participant: {self.accountName}, {self.roomID}, {self.participationStatus}, {self.telegramID}, " \
               f"{self.nftTemplateID}, {self.participantName}"

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

    def isSameCustom(self, other):
        # This is a custom function to compare two participants without comparing the roomID and participantName
        # and TelegramID
        if not isinstance(other, Participant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.accountName == other.accountName and \
               self.participationStatus == other.participationStatus and \
               self.nftTemplateID == other.nftTemplateID

    def overrideCustom(self, other):
        # This is a custom function to override self values with other values without overriding the
        # roomID, participantName and TelegramID
        if not isinstance(other, Participant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        self.accountName = other.accountName
        self.participationStatus = other.participationStatus
        #self.telegramID = other.telegramID
        self.nftTemplateID = other.nftTemplateID


