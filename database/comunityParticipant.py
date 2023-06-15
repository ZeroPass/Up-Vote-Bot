from datetime import datetime
from database.participant import Participant
from transmissionCustom import CustomMember
from sbt import SBT


class CommunityParticipant(Participant):
    # it is only for managing allocation of participants to rooms - not a database object

    def __init__(self, accountName: str, roomID: int, participationStatus: bool, telegramID: str, nftTemplateID: int,
                 participantName: str, sbt: SBT = None, customMember: CustomMember = None):
        assert isinstance(accountName, str), "accountName must be str"
        assert isinstance(roomID, (int, type(None))), "roomID must be int or None"
        assert isinstance(telegramID, str), "telegramID must be str"
        assert isinstance(nftTemplateID, int), "nftTemplateID must be int"
        assert isinstance(participantName, str), "participantName must be str"
        assert isinstance(sbt, (SBT, type(None))), "sbt must be SBT or None"
        assert isinstance(customMember, (CustomMember, type(None))), "customMember must be CustomMember or None"
        super().__init__(accountName, roomID, participationStatus, telegramID, nftTemplateID, participantName)
        self.sbt = sbt
        self.customMember = customMember
        self.knownToBot = None

    @classmethod
    def justSBT(cls, accountName: str, sbt: SBT):
        assert isinstance(accountName, str), "accountName must be str"
        assert isinstance(sbt, SBT), "sbt must be SBT"
        return cls(accountName=accountName,
                   roomID=0,
                   participationStatus=False,
                   telegramID="",
                   nftTemplateID=-1,
                   participantName="",
                   sbt=sbt,
                   customMember=None)

    @classmethod
    def justCustomMember(cls, customMember: CustomMember):
        assert isinstance(customMember, CustomMember), "customMember must be CustomMember"
        return cls(accountName=customMember.userId,
                   roomID=0,
                   participationStatus=False,
                   telegramID="",
                   nftTemplateID=-1,
                   participantName="",
                   sbt=None,
                   customMember=customMember)

    @classmethod
    def justSBTAndCustomMember(cls, accountName: str, sbt: SBT, customMember: CustomMember):
        assert isinstance(accountName, str), "accountName must be str"
        assert isinstance(sbt, SBT), "sbt must be SBT"
        assert isinstance(customMember, CustomMember), "customMember must be CustomMember"
        return cls(accountName=accountName,
                   roomID=0,
                   participationStatus=False,
                   telegramID="",
                   nftTemplateID=-1,
                   participantName="",
                   sbt=sbt,
                   customMember=customMember)

    # customMember - to handle additional data about participant
    def setCustomMember(self, customMember: CustomMember):
        assert isinstance(customMember, CustomMember), "customMember must be CustomMember"
        self.customMember = customMember

    def isCustomMemberSet(self):
        return self.customMember is not None

    def getCustomMember(self):
        if self.customMember is None:
            raise Exception("CustomMember is not set")
        return self.customMember

    # knownToBot is set to True if the participant is known to the bot - just temporary parameter
    # because of optimization
    def isKnownToBotSet(self):
        return self.knownToBot is not None

    def setKnownToBot(self, knownToBot: bool):
        assert isinstance(knownToBot, bool), "knownToBot must be bool"
        self.knownToBot = knownToBot

    def getKnownToBot(self):
        if self.knownToBot is None:
            raise Exception("knownToBot is not set")
        return self.knownToBot

    @classmethod
    def fromParticipant(cls, participant: Participant, customMember: CustomMember):
        assert isinstance(participant, Participant), "participant must be type of Participant"
        assert isinstance(customMember, CustomMember), "customMember must be type of CustomMember"
        return cls(accountName=participant.accountName,
                   roomID=participant.roomID,
                   participationStatus=participant.participationStatus,
                   telegramID=participant.telegramID,
                   nftTemplateID=participant.nftTemplateID,
                   participantName=participant.participantName,
                   sbt=None,
                   customMember=customMember)

    def isSameAndHigherSBTround(self, other):
        # if round in SBT is higher than in other, return True
        assert isinstance(other, CommunityParticipant), "other must be type of CommunityParticipant"
        if self.sbt is None or other.sbt is None:
            return False

        response = super().__eq__(other) and other.sbt.round < self.sbt.round
        # return true if self is is higer than other
        return response

    def isSameWithoutCustomMember(self, other):
        assert isinstance(other, CommunityParticipant), "other must be type of CommunityParticipant"
        return super().__eq__(other) and self.sbt == other.sbt

    def __eq__(self, other):
        if not isinstance(other, CommunityParticipant):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return super().__eq__(other) and self.sbt == other.sbt and self.customMember == other.customMember

    def __str__(self):
        return "accountName: " + self.accountName + \
               "; roomID: " + str(self.roomID) + \
               "; participationStatus: " + str(self.participationStatus) + \
               "; telegramID: " + self.telegramID + \
               "; nftTemplateID: " + str(self.nftTemplateID) + \
               "; participantName: " + self.participantName + \
               "; sbt: " + str(self.sbt) if self.sbt is not None else "None" + \
               "; customMember: " + str(self.customMember)

    __repr__ = __str__
