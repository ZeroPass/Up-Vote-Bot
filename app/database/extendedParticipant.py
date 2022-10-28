from app.database.participant import Participant


class ExtendedParticipant(Participant):
    #it is only for managing allocation of participants to rooms - not a database object

    def __init__(self, accountName: str, roomID: int, participationStatus: bool, telegramID: str, nftTemplateID: int,
                 participantName: str, index: int, voteFor: str = None, participant: Participant = None):
        if participant is not None:
            super().__init__(participant.accountName, participant.roomID, participant.participationStatus,
                             participant.telegramID, participant.nftTemplateID, participant.participantName)
        else:
            assert isinstance(accountName, str), "accountName must be str"
            assert isinstance(roomID, (int, type(None))), "roomID must be int"
            assert isinstance(telegramID, str), "telegramID must be str"
            assert isinstance(nftTemplateID, int), "nftTemplateID must be int"
            assert isinstance(participantName, str), "participantName must be str"
            super().__init__(accountName, roomID, participationStatus, telegramID, nftTemplateID, participantName)
        self.index = index
        self.voteFor = voteFor

    def __eq__(self, other):
        if not isinstance(other, ExtendedParticipant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return super().__eq__(other) and \
               self.index == other.index and \
               self.voteFor == other.voteFor

    def __str__(self):
        return "accountName: " + self.accountName + "\n" + \
               "roomID: " + str(self.roomID) + "\n" + \
               "participationStatus: " + str(self.participationStatus) + "\n" + \
               "telegramID: " + self.telegramID + "\n" + \
               "nftTemplateID: " + str(self.nftTemplateID) + "\n" + \
               "participantName: " + self.participantName + "\n" + \
               "index: " + str(self.index) + "\n" + \
               "voteFor: " + self.voteFor

    def __lt__(self, other):
        return self.index < other.index

