from app.constants import dfuse_api_key
from app.database import Database, Election, Room
from app.log import Log
from app.chain.dfuse import Response, ResponseError, ResponseSuccessful
from app.chain.eden import EdenData
from app.database.participant import Participant
from app.chain.atomicAssets import AtomicAssetsData

class ParticipantsManagementException(Exception):
    pass

LOG = Log(className="ParticipantsManagement")

class ParticipantsManagement:

    def __init__(self, edenData: EdenData):
        self.edenData = edenData
        self.participants = []
        self.database = Database()

    def getElection(self, height: int = None):
        """Get election"""
        try:
            LOG.info("Get election")



        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException("Exception thrown when called getElection; Description: " + str(e))

    def getParticipantsFromChainAndMatchWithDatabase(self, election: Election, height: int = None):
        """Get participants from chain and match with database. Undefined room at this step"""
        try:
            LOG.info("Get participants from chain and match with database")
            participant: list[Participant] = self.getMembersFromChain(height=height)
            room = Room(electionID=election.electionID, roomName="Room pre-election", round=0)
            #self.database.createParticipantsIfNotExists(participants=participant, election=election)
            LOG.debug("Participants created")
            for p in participant:
                LOG.info("Participant: " + str(p))
                #in this case we don't have real room number
                self.database.setMemberWithElectionIDAndWithRoomID(participant=p, election=election, room=room)

            LOG.info("Participants from chain: " + str(self.participants))

        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException("Exception thrown when called getParticipantsFromChainAndMatchWithDatabase; Description: " + str(e))

    """def setMemberifNotExists(self):
        #Get participants from database
        try:
            LOG.info("Set member if not exists")



        except Exception as e:
            LOG.exception(str(e))
            raise ParticipantsManagementException("Exception thrown when called getParticipantsFromDatabase; Description: " + str(e))"""

    def getTelegramID(self, nftTemplateID: int, atomicAssetsData: AtomicAssetsData) -> str:
        """Get telegram ID from nft template ID"""
        try:
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

    def getMembersFromChain(self, height: int = None) -> list[Participant]:
        """Get participants from chain"""
        try:
            response: Response = self.edenData.getMembers(height=height)

            aad = AtomicAssetsData(dfuse_api_key)

            members: list[Participant] = list()
            if isinstance(response, ResponseSuccessful):
                for key, value in response.data.items():
                    #{'account': '1.max', 'name': 'Yang Hao', 'status': 1, 'nft_template_id': '1440',
                    # 'election_participation_status': 0, 'election_rank': 0, 'representative': 'zzzzzzzzzzzzj', 'encryption_key': None}
                    LOG.debug(message="data: " + str(value))
                    LOG.debug(message="data: " + str(value.data[1]))

                    try:
                        member =Participant(accountName=key,
                                    roomID=-1, #not yet
                                    participationStatus = True if len(value.data) == 2 and
                                                            "election_participation_status" in value.data[1] and
                                                            value.data[1]['election_participation_status'] == 1
                                                                else False,
                                    telegramID="",
                                    nftTemplateID=int(value.data[1]['nft_template_id']) if len(value.data) == 2 and
                                                                                        "nft_template_id" in value.data[1] and
                                                                                           value.data[1]['nft_template_id'] is not None
                                                                                        else -1,
                                    participantName=value.data[1]['name'] if len(value.data) == 2 and
                                                                                "name" in value.data[1] and
                                                                                value.data[1]['name'] is not None
                                                                                else "<unknownName>")

                        #set telegram id, if there is known template id, otherwise set -1 -> optimisation
                        member.telegramID = self.getTelegramID(nftTemplateID=member.nftTemplateID, atomicAssetsData=aad) \
                            if member.nftTemplateID != 0 \
                            else "-1"

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

