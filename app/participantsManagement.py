from app.constants import dfuse_api_key
from app.database import Database, Election
from app.database.room import Room
from app.log import Log
from app.chain.dfuse import Response, ResponseError, ResponseSuccessful
from app.chain.eden import EdenData
from app.database.participant import Participant
from app.chain.atomicAssets import AtomicAssetsData
from app.transmission import Communication
from app.transmission.name import ADD_AT_SIGN_IF_NOT_EXISTS


class ParticipantsManagementException(Exception):
    pass

LOG = Log(className="ParticipantsManagement")

class ParticipantsManagement:

    def __init__(self, edenData: EdenData, database: Database, communication: Communication):
        self.edenData = edenData
        self.participants = []
        self.database = database
        self.communication = communication


    def getParticipantsFromChainAndMatchWithDatabase(self, election: Election, height: int = None):
        """Get participants from chain and match with database. Undefined room at this step"""
        try:
            LOG.info("Get participants from chain and match with database")
            room = Room(electionID=election.electionID,
                        roomNameShort="Room p-e",
                        roomNameLong="Room pre-election",
                        round=0,
                        roomIndex=-1,
                        predisposedBy="")
            participants: list[Participant] = self.getMembersFromChain(room=room, height=height)
            #self.database.createParticipantsIfNotExists(participants=participant, election=election)
            LOG.debug("Creating participants if not exists")
            self.database.setMemberWithElectionIDAndWithRoomID(participants=participants, election=election, room=room)

            LOG.info("Participants from chain: " + str(self.participants))

        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException("Exception thrown when called getParticipantsFromChainAndMatchWithDatabase; Description: " + str(e))

    def getTelegramID(self, accountName: str, nftTemplateID: int, atomicAssetsData: AtomicAssetsData) -> str:
        """Get telegram ID from nft template ID"""
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
                return response.data
            else:
                LOG.info("Error: " + str(response))
                raise ParticipantsManagementException("Error: " + str(response.error))
        except Exception as e:
            LOG.exception(str(e))
            #raise ParticipantsManagementException("Exception thrown when called getTelegramID; Description: " + str(e))
            return "-1"

    def getMembersFromChain(self, room: Room, height: int = None) -> list[Participant]:
        """Get participants from chain"""
        try:
            assert isinstance(room, Room), "room must be a Room object"

            response: Response = self.edenData.getMembers(height=height)


            aad = AtomicAssetsData(dfuseApiKey=dfuse_api_key, database=self.database)

            members: list[Participant] = list()
            if isinstance(response, ResponseSuccessful):
                counter = 0
                for key, value in response.data.items():
                    try:
                        #if counter > 20:
                        #    break
                        counter += 1
                        member =Participant(accountName=key,
                                            roomID=-1, #not yet
                                            participationStatus=True if len(value) == 2 and
                                                                    "election_participation_status" in value[1] and
                                                                    value[1]['election_participation_status'] != 0
                                                                        else False,
                                            telegramID="",
                                            nftTemplateID=int(value[1]['nft_template_id']) if len(value) == 2 and
                                                                                                "nft_template_id" in value[1] and
                                                                                                   value[1]['nft_template_id'] is not None
                                                                                                else -1,
                                            participantName=value[1]['name'] if len(value) == 2 and
                                                                                        "name" in value[1] and
                                                                                        value[1]['name'] is not None
                                                                                        else "<unknownName>")

                        #set telegram id, if there is a known template id, otherwise set -1
                        # get telegram id from API only if there is no telegramID entry in database -> optimisation
                        member.telegramID = self.getTelegramID(accountName=member.accountName,
                                                               nftTemplateID=member.nftTemplateID,
                                                               atomicAssetsData=aad) \
                            if member.nftTemplateID != 0 \
                            else "-1"
                        #if member.telegramID != "-1":
                        #    if self.communication.userExists(userID=ADD_AT_SIGN_IF_NOT_EXISTS(member.telegramID)) == False:
                        #        member.telegramID = "-2"

                    except Exception as e:
                        LOG.exception(str(e))

                    members.append(member)
                    LOG.info("Member: " + str(key))
                LOG.info("Member from chain: " + str(self.participants))
                return members
            LOG.info("Get participants from chain")
        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException("Exception thrown when called getParticipantsFromChain; Description: " + str(e))

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

