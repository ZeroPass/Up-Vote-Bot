# install grpcio-tools
import threading
# from struct import Struct
import time
from datetime import datetime, timedelta

from app.chain.dfuse import DfuseConnection, ResponseError, Response, ResponseSuccessful
from app.constants import eden_account, dfuse_api_key
from app.database import Database
from app.log.log import Log
import requests as requests
import json
import schedule


class ResponseException(Exception):
    pass


LOG = Log(className="EdenChain")


class EdenData:
    # dfusConnection and database should be initialized at the beginning of the program - because of the threading
    dfuseConnection: DfuseConnection

    def __init__(self, dfuseConnection: DfuseConnection):
        LOG.info("Initialization of EdenChain")
        assert isinstance(dfuseConnection, DfuseConnection), "dfuseConnection is not of type DfuseConnection"
        #assert isinstance(database, Database), "database is not of type Database"
        self.dfuseConnection = dfuseConnection

        # update api key
        self.updateDfuseApiKey(database=dfuseConnection.database)
        schedule.every(120).minutes.do(self.updateDfuseApiKey1, database=dfuseConnection.database)
        # must be set as variable
        self.stop_run_continuously = self.run_continuously()

    def run_continuously(self, interval: int = 1):
        """Continuously run, while executing pending jobs at each
        elapsed time interval.
        @return cease_continuous_run: threading. Event which can
        be set to cease continuous run. Please note that it is
        *intended behavior that run_continuously() does not run
        missed jobs*. For example, if you've registered a job that
        should run every minute and you set a continuous run
        interval of one hour then your job won't be run 60 times
        at each interval but only once.
        """
        cease_continuous_run = threading.Event()

        class ScheduleThread(threading.Thread):
            @classmethod
            def run(cls):
                while not cease_continuous_run.is_set():
                    schedule.run_pending()
                    time.sleep(interval)

        continuous_thread = ScheduleThread()
        continuous_thread.start()
        return cease_continuous_run


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
            return ResponseError("Exception thrown when called getCurrentElectionState; Description: " + str(e))

    def getParticipants(self, height: int = None):
        try:
            LOG.info("Get election state on height: " + str(height) if height is not None else "<current/live>")
            ACCOUNT = eden_account
            TABLE = 'votes'
            SCOPE = None

            return self.dfuseConnection.getTable(account=ACCOUNT,
                                                 table=TABLE,
                                                 scope=SCOPE,
                                                 height=height,
                                                 propagateJson=True)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getParticipants; Description: " + str(e))

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
            assert isinstance(timestamp, datetime), "timestamp is not of type datetime"
            LOG.info("Get block number on datetime: " + timestamp.strftime("%Y-%m-%d %H:%M:%S"))
            return self.dfuseConnection.getBlockHeightFromTimestamp(timestamp=timestamp)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getBlockNumOfTimestamp; Description: " + str(e))

    def getVotes(self, height: int = None):
        try:
            LOG.info("Get votes on height: " + str(height) if height is not None else "<current/live>")
            ACCOUNT = eden_account
            TABLE = 'votes'
            SCOPE = None

            return self.dfuseConnection.getTable(account=ACCOUNT,
                                                 table=TABLE,
                                                 scope=SCOPE,
                                                 height=height,
                                                 propagateJson=True)


        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getVotes; Description: " + str(e))
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

    def getChainHeadBlockNumber(self):
        try:
            path = '/v1/chain/get_info'
            LOG.info("Path: " + path)

            resultTable = requests.get(self.dfuseConnection.linkNode(path=path))

            j = json.loads(resultTable.text)
            LOG.debug("Result: " + str(j))
            return int(j['head_block_num'])

        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getChainDatetime; Description: " + str(e))

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
    def updateDfuseApiKey1(self, database: Database):
        LOG.debug("Update dfuse api key. Sheduled function.")
        self.updateDfuseApiKey(database=database)
    def updateDfuseApiKey2(self, database: Database):
        LOG.error("FROM main thread")
        #self.updateDfuseApiKey(database=database)
        database.checkIfTokenExpired("dfuse", executionTime=datetime(2020, 1, 1, 12, 0))

    def updateDfuseApiKey(self, database: Database):
        try:
            assert isinstance(database, Database), "database is not of type Database"
            LOG.debug("Updating dfuse api key if necessary")
            if database.checkIfTokenExists(name="dfuse") is False:
                LOG.debug("Token does not exist, create it")
                tokenAndExpireDate: () = self.dfuseConnection.connect()
                database.writeToken(name="dfuse",
                                    value=tokenAndExpireDate[0],
                                    expireBy=tokenAndExpireDate[1] - timedelta(hours=6))
                self.dfuseConnection.dfuseToken = tokenAndExpireDate[0]

            elif database.checkIfTokenExpired(name="dfuse", executionTime=self.getChainDatetime()):
                # token exists but is expired, update it
                LOG.debug("Token exists but is expired, update it")
                tokenAndExpireDate: () = self.dfuseConnection.connect()
                database.writeToken(name="dfuse",
                                    value=tokenAndExpireDate[0],
                                    expireBy=tokenAndExpireDate[1] - timedelta(hours=6))
                self.dfuseConnection.dfuseToken = tokenAndExpireDate[0]

            elif self.dfuseConnection.dfuseToken is None:
                # token exists, and it is valid (checked in previous el(if) statements) but is not set, set it
                LOG.debug("token exists and it is valid (checked in previous el(if) statements) but is not set, set it")
                self.dfuseConnection.dfuseToken = database.getToken(name="dfuse")

            else:
                LOG.debug("Token exists and it is not expired, use it")
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called updateDfuseApiKey; Description: " + str(e))


def main():
    print("Hello World!")
    database = Database()
    dfuseConnection = DfuseConnection(dfuseApiKey=dfuse_api_key, database=database)

    edenData: EdenData = EdenData(dfuseConnection=dfuseConnection)

    test = edenData.getVotes(height=272119950 + 100)
    ret = 9

if __name__ == "__main__":
    main()
