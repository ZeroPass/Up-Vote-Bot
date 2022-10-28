from app.chain.eden import EdenData
from app.log import Log

LOG = Log(className="DateTimeManagement")

class DateTimeManagement(Exception):
    pass

class DateTimeManagement:

    def __init__(self, edenData: EdenData):
        if edenData is None:
            raise DateTimeManagement("DateTimeManagement.init; EdenData must be initialized")
        self.edenData = edenData
        pass

    def getTime(self):
        try:
            LOG.info("Get time")
            return self.edenData.getChainDatetime()
        except Exception as e:
            LOG.exception(str(e))
            raise DateTimeManagement("Exception thrown when called getTime; Description: " + str(e))
