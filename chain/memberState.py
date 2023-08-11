from log import Log

LOG = Log(className="MemberState")

class ElectCurrTableException(Exception):
    pass

# { "account": "1.max", "name": "Yang Hao", "status": 1, "nft_template_id": 1440, "election_participation_status": 0,
# "election_rank": 0, "representative": "zzzzzzzzzzzzj", "encryption_key": null }
class MemberState:
    def __init__(self, receivedData: dict):
        assert isinstance(receivedData, list), "data is not a list"
        assert len(receivedData) == 2, "data is not a list of length 2"
        assert isinstance(receivedData[0], str), "data[0] is not a string"
        assert isinstance(receivedData[1], dict), "data[1] is not a dict"
        LOG.debug("Member state(table) initialized: " + str(receivedData))
        self.type: str = receivedData[0]
        self.data: dict = receivedData[1]

    def getType(self) -> str:
        return self.type

    def getAccount(self) -> str:
        return self.data["account"]

    def getName(self) -> str:
        return self.data["name"]

    def getStatus(self) -> int:
        return self.data["status"]

    def getNftTemplateId(self) -> int:
        return self.data["nft_template_id"]

    def getElectionParticipationStatus(self) -> int:
        return self.data["election_participation_status"]

    def getElectionRank(self) -> int:
        return self.data["election_rank"]

    def getRepresentative(self) -> str:
        return self.data["representative"]

    def getEncryptionKey(self) -> str:
        return self.data["encryption_key"]
