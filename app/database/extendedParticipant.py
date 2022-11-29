from app.database.participant import Participant


class ExtendedParticipant(Participant):
    #it is only for managing allocation of participants to rooms - not a database object

    def __init__(self, accountName: str, roomID: int, participationStatus: bool, telegramID: str, nftTemplateID: int,
                 participantName: str, index: int, voteFor: str = None):
        assert isinstance(accountName, str), "accountName must be str"
        assert isinstance(roomID, (int, type(None))), "roomID must be int or None"
        assert isinstance(telegramID, str), "telegramID must be str"
        assert isinstance(nftTemplateID, int), "nftTemplateID must be int"
        assert isinstance(participantName, str), "participantName must be str"
        super().__init__(accountName, roomID, participationStatus, telegramID, nftTemplateID, participantName)
        self.index = index
        self.voteFor = voteFor

    @classmethod
    def fromParticipant(cls, participant: Participant, index: int, voteFor: str = None):
        assert isinstance(participant, Participant), "participant must be of type Participant"
        assert isinstance(index, int), "index must be int"
        assert isinstance(voteFor, (str, type(None))), "voteFor must be str or None"
        return cls(accountName=participant.accountName,
                   roomID=participant.roomID,
                   participationStatus=participant.participationStatus,
                   telegramID=participant.telegramID,
                   nftTemplateID=participant.nftTemplateID,
                   participantName=participant.participantName,
                   index=index,
                   voteFor=voteFor)

    def __eq__(self, other):
        if not isinstance(other, ExtendedParticipant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return super().__eq__(other) and \
               self.index == other.index and \
               self.voteFor == other.voteFor

    def __str__(self):
        return "accountName: " + self.accountName + \
               "; roomID: " + str(self.roomID) + \
               "; participationStatus: " + str(self.participationStatus) + \
               "; telegramID: " + self.telegramID + \
               "; nftTemplateID: " + str(self.nftTemplateID) + \
               "; participantName: " + self.participantName + \
               "; index: " + str(self.index) + \
               "; voteFor: " + self.voteFor if self.voteFor is not None else "None"

    def __lt__(self, other):
        return self.index < other.index

