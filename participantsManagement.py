from enum import Enum

from constants import dfuse_api_key
from database import Database, Election
from database.room import Room
from log import Log
from chain.dfuse import Response, ResponseError, ResponseSuccessful
from chain.eden import EdenData
from database.participant import Participant
from chain.atomicAssets import AtomicAssetsData
from transmission import Communication
from transmission.name import PARSE_TG_NAME


class ParticipantListManagementException(Exception):
    pass


class ParticipantsManagementException(Exception):
    pass

LOG = Log(className="ParticipantsManagement")
LOGplm = Log(className="ParticipantListManagement")

class ListItemValue(Enum):
    NONE = 0
    DB = 1
    CHAIN = 2
    BOTH = 3

class WaitingRoom:
    #because of Specific values of the roomIndex you must always use this class to get Preelection Room
    def __init__(self, database: Database, dummyElection: Election):
        #make sure that dummy election has correct CurrentElectionState = CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS
        assert isinstance(database, Database), "database is not a Database"
        assert isinstance(dummyElection, Election), "election is not a Election"
        self.database = database
        self.election = dummyElection
        self.roomFromDB = None

        # must be called at the end of __init__
        self.defineRoom()

    def defineRoom(self) -> Room:
        # like DB static variable for waiting room
        self.room = Room(electionID=self.election.electionID,
                         roomNameShort="Room p-e",
                         roomNameLong="Room pre-election",
                         round=0,
                         roomIndex=-50,
                         predisposedBy="BotWaitingRoom")

    def getRoomFromDB(self) -> Room:
        # or create if not created yet
        if isinstance(self.roomFromDB, Room):
            #already created
            return self.roomFromDB
        else:
            #not yet created
            room = self.database.createWaitingRoomOrGetExisting(self.election, self.room)
            if room is None:
                LOG.exception("Waiting room is not defined")
                raise ParticipantsManagementException("Waiting room is not defined")
            self.roomFromDB = room
            return self.roomFromDB

    def getRoom(self) -> Room:
        #if room is not defined in DB it returns None
        return self.database.getRoomWaitingRoom(self.election, self.room)



class ParticipantListItem:
    def __init__(self, participantDB: Participant = None,
                 participantChain: Participant = None):
        assert isinstance(participantDB, (Participant, type(None))), "participantDB is not a Participant or None"
        assert isinstance(participantChain, (Participant, type(None))), "participantChain is not a Participant or None"

        self.participantDB = participantDB
        self.participantChain = participantChain

    def getDB(self) -> Participant:
        return self.participantDB

    def getChain(self) -> Participant:
        return self.participantChain

    def addDB(self, participantDB: Participant):
        assert isinstance(participantDB, Participant), "participantDB is not a Participant"
        assert self.participantDB is None, "participantDB is not None"
        self.participantDB = participantDB

    def addChain(self, participantChain: Participant):
        assert isinstance(participantChain, Participant), "participantChain is not a Participant"
        assert self.participantChain is None, "participantChain is not None"
        self.participantChain = participantChain

    def compare(self) -> bool:
        if self.hasValue() == ListItemValue.BOTH:
            return True if self.participantDB.isSameCustom(self.participantChain) else False
        else:
            return False

    def hasValue(self):
        if self.participantDB is None and self.participantChain is not None:
            return ListItemValue.CHAIN
        elif self.participantDB is not None and self.participantChain is None:
            return ListItemValue.DB
        elif self.participantDB is not None and self.participantChain is not None:
            return ListItemValue.BOTH
        else:
            return ListItemValue.NONE


class ParticipantListManagement:

    def __init__(self, databaseList: list[Participant], chainList: list[Participant]):
        assert isinstance(databaseList, list), "databaseList is not a list"
        assert isinstance(chainList, list), "chainList is not a list"
        self.merged = {}
        self.merge(databaseList, chainList)

    def merge(self, databaseList: list[Participant], chainList: list[Participant]):
        """Merge two lists of participants"""
        try:
            LOG.info("Merge two lists of participants")
            for participantDB in databaseList:
                if participantDB.accountName not in self.merged:
                    self.merged[participantDB.accountName] = ParticipantListItem(participantDB=participantDB)
                else:
                    self.merged[participantDB.accountName].addDB(participantDB)

            for participantChain in chainList:
                if participantChain.accountName not in self.merged:
                    self.merged[participantChain.accountName] = ParticipantListItem(participantChain=participantChain)
                else:
                    self.merged[participantChain.accountName].addChain(participantChain)

            counterDB, counterChain, counterBoth = 0, 0, 0
            for item in self.merged:
                if self.merged[item].hasValue() == ListItemValue.DB:
                    counterDB += 1
                elif self.merged[item].hasValue() == ListItemValue.CHAIN:
                    counterChain += 1
                elif self.merged[item].hasValue() == ListItemValue.BOTH:
                    counterBoth += 1
            LOGplm.debug("Merged data counter; Both : " + str(counterBoth) +
                         ", Only on chain: " + str(counterChain) +
                         ", Only in DB: " + str(counterDB) +
                         ", Total: " + str(counterBoth + counterChain + counterDB))

        except Exception as e:
            LOGplm.exception("Exception thrown when called merge; " + str(e))
            raise ParticipantListManagementException("Exception thrown when called merge; Description: " + str(e))

    def getByAccountName(self, accountName: str) -> ParticipantListItem:
        """Get participant by account name"""
        assert isinstance(accountName, str), "accountName is not a string"
        try:
            LOGplm.debug("Get participant by account name")
            if accountName in self.merged:
                return self.merged[accountName]
            else:
                return None
        except Exception as e:
            LOGplm.exception("Exception thrown when called getByAccountName; " + str(e))
            raise ParticipantListManagementException(
                "Exception thrown when called getByAccountName; Description: " + str(e))

    def getAll(self) -> dict[str, ParticipantListItem]:
        """Get all participants"""
        try:
            LOGplm.debug("Get all participants")
            return self.merged
        except Exception as e:
            LOGplm.exception("Exception thrown when called getAll; " + str(e))
            raise ParticipantListManagementException("Exception thrown when called getAll; Description: " + str(e))


class ParticipantsManagement:
    def __init__(self, edenData: EdenData, database: Database, communication: Communication):
        self.edenData = edenData
        self.participants = []
        self.database = database
        self.communication = communication

    def getOnlyDiffCustom(self, participantsChain: list[Participant], participantsDB: list[Participant]) -> \
            list[Participant]:
        """Compare participant lists: telegramID not affected at all (also roomID and name)"""
        try:
            LOG.info("Compare participant lists. Remove duplicates")
            plm: ParticipantListManagement = ParticipantListManagement(databaseList=participantsDB,
                                                                       chainList=participantsChain)

            accounts: dict[str, ParticipantListItem] = plm.getAll()
            for key, value in accounts.copy().items():
                if value.hasValue() == ListItemValue.BOTH:
                    if value.compare() and value.participantDB.telegramID != "":  # custom compare - not all values are compared
                        accounts.pop(key)


            # accounts dict: only accounts that are different in chain and db left
            updatedParticipants: list[Participant] = []
            for key, value in accounts.items():
                if value.hasValue() == ListItemValue.CHAIN:  # only in chain
                    updatedParticipants.append(value.participantChain)
                if value.hasValue() == ListItemValue.DB:  # only in db
                    LOG.error("Participant " + value.participantDB.accountName + " is not on chain anymore.")
                elif value.hasValue() == ListItemValue.BOTH:  # on both but different
                    # override custom values from db with values from chain
                    value.participantDB.overrideCustom(value.participantChain)
                    if value.participantDB.nftTemplateID > 0:
                        updatedParticipants.append(value.participantDB)


            return updatedParticipants
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException(
                "Exception thrown when called compareParticipantLists; Description: " + str(e))

    def getParticipantsFromChainAndMatchWithDatabase(self, election: Election, height: int = None):
        """Get participants from chain and match with database. Undefined room at this step"""
        try:
            LOG.info("Get participants from chain and match with database")
            dummyElectionForFreeRooms: Election = self.database.getDummyElection(election=election)
            if dummyElectionForFreeRooms is None:
                raise ParticipantsManagementException("No dummy election set in database")

            room = WaitingRoom(database=self.database, dummyElection=dummyElectionForFreeRooms).getRoomFromDB()

            participantsChain: list[Participant] = self.getMembersFromChain(room=room, height=height)
            participantsDB: list[Participant] = self.getParticipantsFromDatabase(room=room)

            # only participants that are different in chain and db
            participants: list[Participant] = self.getOnlyDiffCustom(participantsChain=participantsChain,
                                                                     participantsDB=participantsDB)

            aad = AtomicAssetsData(dfuseApiKey=dfuse_api_key, database=self.database)

            # add telegramID to participants if not yet set
            for participant in participants:
                if self.updateTelegramIDIfNotExists(participant=participant, atomicAssetsData=aad):
                    LOG.info("Participant's telegramID " + participant.accountName + " has been updated")

            LOG.debug("Creating (updating) participants")
            self.database.setMemberWithElectionIDAndWithRoomID(participants=participants, election=election, room=room)
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException(
                "Exception thrown when called getParticipantsFromChainAndMatchWithDatabase; Description: " + str(e))

    def getMembersFromDBTotal(self, election: Election) -> list[Participant]:
        """Get members from database"""
        try:
            dummyElectionForFreeRooms: Election = self.database.getDummyElection(election=election)
            if dummyElectionForFreeRooms is None:
                raise ParticipantsManagementException("No dummy election set in database")

            room = WaitingRoom(database=self.database, dummyElection=dummyElectionForFreeRooms).getRoomFromDB()
            total: int = self.database.getMembersWhoParticipateInElectionCount(room=room)
            LOG.info("Number of participants who participated in database: " + str(total))
            return total
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException(
                "Exception thrown when called getMembersFromDBTotal; Description: " + str(e))

    def getTelegramID(self, accountName: str, nftTemplateID: int, atomicAssetsData: AtomicAssetsData) -> str:
        """Get telegram ID from nft template ID"""
        assert isinstance(accountName, str), "accountName is not a string"
        assert isinstance(nftTemplateID, int), "nftTemplateID is not an int"
        assert isinstance(atomicAssetsData, AtomicAssetsData), "atomicAssetsData is not an AtomicAssetsData object"
        try:
            LOG.debug("Get telegram ID from nft template ID")
            participant = self.database.getParticipant(accountName=accountName)
            if isinstance(participant, Participant):
                LOG.debug("Participant found in database")
                if participant.telegramID != "":
                    LOG.debug("Telegram ID (" + participant.telegramID + ") found in database, do not call API")
                    return participant.telegramID

            LOG.info("Get telegram id with nft template id: " + str(nftTemplateID))
            response = atomicAssetsData.getTGfromTemplateID(templateID=nftTemplateID)
            if isinstance(response, ResponseSuccessful):
                return PARSE_TG_NAME(response.data)
            else:
                LOG.info("Error: " + str(response))
                raise ParticipantsManagementException("Error: " + str(response.error))
        except Exception as e:
            LOG.exception(str(e))
            # raise ParticipantsManagementException("Exception thrown when called getTelegramID; Description: " + str(e))
            return "-1"

    def updateTelegramIDIfNotExists(self, participant: Participant, atomicAssetsData: AtomicAssetsData) -> bool:
        """Get telegram ID if not exists, return true if telegram ID is set otherwise false"""
        assert isinstance(participant, Participant), "Participant is not instance of Participant"
        assert isinstance(atomicAssetsData, AtomicAssetsData), "AtomicAssetsData is not instance of AtomicAssetsData"
        try:
            LOG.debug("Get telegram ID if not exists")
            if participant.nftTemplateID == None or participant.nftTemplateID <= 0:
                LOG.error("NFT template ID not found, do not call API")
                return False

            if participant.telegramID == "" or participant.telegramID == "-1":
                LOG.debug("Telegram ID not found in database, call API")
                LOG.info("Get telegram id with nft template id: " + str(participant.nftTemplateID))
                response = atomicAssetsData.getTGfromTemplateID(templateID=participant.nftTemplateID)
                if isinstance(response, ResponseSuccessful):
                    participant.telegramID = PARSE_TG_NAME(response.data)
                    return True
                else:
                    LOG.info("Error: " + str(response))
                    participant.telegramID = "-1"
                    return False
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException(
                "Exception thrown when called getTelegramIDIfNotExists; Description: " + str(e))

    def getParticipantsFromDatabase(self, room: Room):
        """Get participants from database"""
        assert isinstance(room, Room), "room must be a Room object"
        try:
            LOG.info("Get participants from database")
            participants: list[Participant] = self.database.getMembersInRoom(room=room)
            LOG.info("Participants from database: " + str(participants))
            return participants
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException(
                "Exception thrown when called getParticipantsFromDatabase; Description: " + str(e))

    def getMembersFromChain(self, room: Room, height: int = None) -> list[Participant]:
        """Get participants from chain"""
        try:
            assert isinstance(room, Room), "room must be a Room object"

            response: Response = self.edenData.getMembers(height=height)

            members: list[Participant] = list()
            if isinstance(response, ResponseSuccessful):
                counter = 0
                for key, value in response.data.items():
                    try:
                        counter += 1
                        member: Participant = Participant(accountName=key,
                                                          roomID=room.roomID,  # not yet
                                                          participationStatus=True if len(value) == 2 and
                                                                                      "election_participation_status" in
                                                                                      value[1] and
                                                                                      value[1][
                                                                                          'election_participation_status'] != 0
                                                          else False,
                                                          telegramID="",
                                                          nftTemplateID=int(value[1]['nft_template_id']) if
                                                          len(value) == 2 and
                                                          "nft_template_id" in value[1] and
                                                          value[1]['nft_template_id'] is not None
                                                          else -1,
                                                          participantName=value[1]['name'] if len(value) == 2 and
                                                                                              "name" in value[1] and
                                                                                              value[1][
                                                                                                  'name'] is not None
                                                          else "<unknownName>")

                        # set telegram id, if there is a known template id, otherwise set -1
                        # get telegram id from API only if there is no telegramID entry in database -> optimisation
                        # member.telegramID = self.getTelegramID(accountName=member.accountName,
                        #                                       nftTemplateID=member.nftTemplateID,
                        #                                       atomicAssetsData=aad) \
                        #    if member.nftTemplateID != 0 \
                        #    else "-1"

                    except Exception as e:
                        LOG.exception("Exception thrown when called getMembersFromChain.inner for loop" + str(e))

                    members.append(member)
                    LOG.info("Member: " + str(key))
                LOG.info("Member from chain: " + str(self.participants))
                return members
            LOG.info("Get participants from chain")
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException(
                "Exception thrown when called getParticipantsFromChain; Description: " + str(e))

    def checkReminders(self, height: int = None):
        """Check if there is need to send reminder"""
        try:
            LOG.info("Check if there is need to send reminder")
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException("Exception thrown when called checkReminders; Description: " + str(e))


def main():
    print("Hello World!")
    dfuseObj = EdenData(dfuseApiKey=dfuse_api_key)
    pm = ParticipantsManagement(edenData=dfuseObj)
    ker = pm.getParticipantsFromChainAndMatchWithDatabase()


if __name__ == "__main__":
    main()
