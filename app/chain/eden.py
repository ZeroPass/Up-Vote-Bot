# install grpcio-tools


# from struct import Struct

from datetime import datetime
from app.chain.dfuse import DfuseConnection, ResponseError, Response
from app.constants import eden_account, dfuse_api_key
from app.log.log import Log
import requests as requests
import json


class ResponseException(Exception):
    pass


LOG = Log(className="EdenChain")


class EdenData:
    dfuseConnection: DfuseConnection

    def __init__(self, dfuseApiKey: str):
        LOG.info("Initialization of EdenChain")
        self.dfuseConnection = DfuseConnection(dfuseApiKey=dfuseApiKey)

    def getElectionState(self, height: int = None) -> Response:
        try:
            LOG.info("Get election state on height: " + str(height) if height is not None else "<current/live>")
            ACCOUNT = eden_account
            TABLE = 'elect.state'
            PRIMARY_KEY = 'elect.state'
            SCOPE = None

            return self.dfuseConnection.getTableRow(account=ACCOUNT,
                                                    table=TABLE,
                                                    primaryKey=PRIMARY_KEY,
                                                    scope=SCOPE,
                                                    height=height)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getElectionState; Description: " + str(e))

    def getCurrentElectionState(self, height: int = None):
        try:
            LOG.info("Get current election state on height: " + str(height) if height is not None else "<current/live>")
            ACCOUNT = eden_account
            TABLE = 'elect.curr'
            PRIMARY_KEY = 'elect.curr'
            SCOPE = None

            return self.dfuseConnection.getTableRow(account=ACCOUNT,
                                                    table=TABLE,
                                                    primaryKey=PRIMARY_KEY,
                                                    scope=SCOPE,
                                                    height=height)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getNextElectionTime; Description: " + str(e))

    def getParticipants(self, height: int = None):
        try:
            LOG.info("Get election state on height: " + str(height) if height is not None else "<current/live>")
            ACCOUNT = eden_account
            TABLE = 'votes'
            SCOPE = None

            return self.dfuseConnection.getTable(account=ACCOUNT,
                                                 table=TABLE,
                                                 scope=SCOPE,
                                                 height=height)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getElectionState; Description: " + str(e))

    def getMembers(self, height: int = None):
        try:
            LOG.info("Get members on height: " + str(height) if height is not None else "<current/live>")
            ACCOUNT = eden_account
            TABLE = 'member'
            SCOPE = None

            return self.dfuseConnection.getTable(account=ACCOUNT,
                                                 table=TABLE,
                                                 scope=SCOPE,
                                                 height=height)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getMembers; Description: " + str(e))

    def getBlockNumOfTimestamp(self, timestamp: datetime) -> Response:
        try:
            LOG.info("Get block number on datetime: " + str(datetime))
            assert (timestamp is not None)
            assert (isinstance(timestamp, datetime))
            return self.dfuseConnection.getBlockHeightFromTimestamp(timestamp=timestamp)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getBlockNumOfTimestamp; Description: " + str(e))

    def getDifferenceBetweenNodeAndServerTime(self, serverTime: datetime, nodeTime: datetime):
        try:
            LOG.info("Get difference between node and server time")
            # get difference, add 15 minutes to be sure that hours are up rounded, return hours
            diff = nodeTime - serverTime
            isInPast = False
            if (diff.days < 0):
                isInPast = True
                diff = serverTime - nodeTime

            return round((diff.seconds) / -3600) if isInPast else round((diff.seconds) / 3600)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError(
                "Exception thrown when called getDifferenceBetweenNodeAndServerTime; Description: " + str(e))

    def getTimestampOfBlock(self, blockNum: int) -> datetime:
        try:
            path = '/v1/chain/get_block'
            LOG.info("Path: " + path)

            resultTable = requests.post(self.dfuseConnection.linkNode(path=path), json={"block_num_or_id": blockNum})
            j = json.loads(resultTable.text)
            return datetime.fromisoformat(j['timestamp'])
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getTimestampOfBlock; Description: " + str(e))

    def getChainDatetime(self):
        try:
            path = '/v1/chain/get_info'
            LOG.info("Path: " + path)

            resultTable = requests.get(self.dfuseConnection.linkNode(path=path))

            j = json.loads(resultTable.text)
            LOG.debug("Result: " + str(j))
            return datetime.fromisoformat(j['head_block_time'])

        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getChainDatetime; Description: " + str(e))


def main():
    print("Hello World!")
    dfuseObj = EdenData(dfuseApiKey=dfuse_api_key)

    resnevem = dfuseObj.getTimestampOfBlock(1312423)
    nodeTime = dfuseObj.getChainDatetime()
    kva = dfuseObj.getDifferenceBetweenNodeAndServerTime(serverTime=datetime.now(),
                                                         nodeTime=datetime.fromisoformat(nodeTime))

    ret = 9


if __name__ == "__main__":
    main()
