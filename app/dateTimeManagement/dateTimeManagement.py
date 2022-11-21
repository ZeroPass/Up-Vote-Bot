from datetime import datetime

from app.chain.eden import EdenData
from app.log import Log
import time

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

    @staticmethod
    def getUnixTimestampInDT() -> datetime:
        try:
            LOG.info("Get unix timestamp")
            return datetime.fromtimestamp(time.time())
        except Exception as e:
            LOG.exception(str(e))
            raise DateTimeManagement("Exception thrown when called getUnixTimestampDT; Description: " + str(e))

