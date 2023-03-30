from datetime import datetime

from log import Log

LOG = Log(className="ElectCurrTable")

class ElectCurrTableException(Exception):
    pass

# { "lead_representative": "someone", "board": [ "member0", "member1", "member2", "member3" ],
#   "last_election_time": "2023-01-07T13:00:00.000" }
class ElectCurrTable:
    def __init__(self, receivedData: dict):
        assert isinstance(receivedData, list), "data is not a list"
        assert len(receivedData) == 2, "data is not a list of length 2"
        assert isinstance(receivedData[0], str), "data[0] is not a string"
        assert isinstance(receivedData[1], dict), "data[1] is not a dict"
        LOG.debug("ElectCurrTable initialized: " + str(receivedData))
        self.type: str = receivedData[0]
        self.data: dict = receivedData[1]

    def getType(self) -> str:
        return self.type

    def getLeadRepresentative(self) -> str:
        return self.data["lead_representative"]

    def getBoard(self) -> list:
        return self.data["board"]

    def getLastElectionTime(self) -> datetime:
        try:
            lastElectionTime: str = self.data["last_election_time"]
            LOG.info("Last election time: " + str(lastElectionTime))
            return datetime.fromisoformat(lastElectionTime)
        except Exception as e:
            LOG.exception("Exception while getting or translating last election time: " + str(e))
            return None