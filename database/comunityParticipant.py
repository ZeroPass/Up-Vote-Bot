from database.participant import Participant


class SBT:
    def __init__(self, sbt: int):
        assert isinstance(sbt, int), "sbt must be int"
        self.sbt = sbt
        self.test = "abc"

    def __eq__(self, other):
        #TODO: must be implemented
        if not isinstance(other, sbt):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.sbt == other.sbt

    def __str__(self):
        #TODO: must be implemented
        return "sbt: " + str(self.sbt) + "; test: " + self.test

    def __lt__(self, other):
        return self.sbt < other.sbt

class CommunityParticipant(Participant):
    #it is only for managing allocation of participants to rooms - not a database object

    def __init__(self, accountName: str, roomID: int, participationStatus: bool, telegramID: str, nftTemplateID: int,
                 participantName: str, sbt: SBT):
        assert isinstance(accountName, str), "accountName must be str"
        assert isinstance(roomID, (int, type(None))), "roomID must be int or None"
        assert isinstance(telegramID, str), "telegramID must be str"
        assert isinstance(nftTemplateID, int), "nftTemplateID must be int"
        assert isinstance(participantName, str), "participantName must be str"
        assert isinstance(sbt, SBT), "sbt must be SBT"
        super().__init__(accountName, roomID, participationStatus, telegramID, nftTemplateID, participantName)
        self.sbt = sbt

    @classmethod
    def fromParticipant(cls, participant: Participant, sbt: SBT):
        assert isinstance(participant, Participant), "participant must be type of Participant"
        assert isinstance(sbt, SBT), "sbt must be SBT"
        return cls(accountName=participant.accountName,
                   roomID=participant.roomID,
                   participationStatus=participant.participationStatus,
                   telegramID=participant.telegramID,
                   nftTemplateID=participant.nftTemplateID,
                   participantName=participant.participantName,
                   sbt=sbt)

    def __eq__(self, other):
        if not isinstance(other, CommunityParticipant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return super().__eq__(other) and \
               self.sbt == other.sbt

    def __str__(self):
        return "accountName: " + self.accountName + \
               "; roomID: " + str(self.roomID) + \
               "; participationStatus: " + str(self.participationStatus) + \
               "; telegramID: " + self.telegramID + \
               "; nftTemplateID: " + str(self.nftTemplateID) + \
               "; participantName: " + self.participantName + \
               "; sbt: " + str(self.sbt)

