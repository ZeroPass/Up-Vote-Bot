# install grpcio-tools
import re
import threading
# from struct import Struct
import time
from datetime import datetime, timedelta

from chain.dfuse.graphqlApi import GraphQLApi

from chain.dfuse import DfuseConnection, ResponseError, Response, ResponseSuccessful
from constants import eden_account, dfuse_api_key
from database import Database
from database.participant import Participant
from database.comunityParticipant import CommunityParticipant as CommunityParticipantDB
from sbt import SBT
from log.log import Log
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
        # assert isinstance(database, Database), "database is not of type Database"
        self.dfuseConnection = dfuseConnection

        # update api key
        self.updateDfuseApiKey(database=dfuseConnection.database)
        self.dfuseConnection.initContractDeserializer()
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
            LOG.info("Path (getChainHeadBlockNumber): " + path)

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
            LOG.info("Path (getChainDatetime): " + path)

            resultTable = requests.get(self.dfuseConnection.linkNode(path=path))

            j = json.loads(resultTable.text)
            LOG.debug("Result: " + str(j))
            return datetime.fromisoformat(j['head_block_time'])

        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getChainDatetime; Description: " + str(e))

    def updateDfuseApiKey1(self, database: Database):
        LOG.debug("Update dfuse api key. Scheduled function.")
        self.updateDfuseApiKey(database=database)

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

    def getGivenSBT(self, contractAccount: str, startTime: datetime, endTime: datetime) -> Response:
        assert isinstance(contractAccount, str), "contractAccount is not of type str"
        assert isinstance(startTime, datetime), "startTime is not of type datetime"
        assert isinstance(endTime, datetime), "endTime is not of type datetime"
        try:
            if startTime > endTime:
                return ResponseError("Start time is after end time")

            startTimeResponse = self.getBlockNumOfTimestamp(timestamp=startTime)
            if isinstance(startTimeResponse, ResponseSuccessful):
                startTimeBlockNum = startTimeResponse.data
            else:
                return ResponseError("Could not get block number of start time:" + str(startTime))

            endTimeResponse = self.getBlockNumOfTimestamp(timestamp=endTime)
            if isinstance(endTimeResponse, ResponseSuccessful):
                endTimeBlockNum = endTimeResponse.data
            else:
                return ResponseError("Could not get block number of end time:" + str(endTime))

            if isinstance(startTimeBlockNum, int) == False or isinstance(endTimeBlockNum, int) == False:
                return ResponseError("Could not get block number of start time or end time - wrong type")

            graphql: GraphQLApi = GraphQLApi(dfuseConnection=self.dfuseConnection)
            return graphql.getGivenSBT(account=contractAccount,
                                       startBlockNum=259815910,  # startTimeBlockNum,
                                       endBlockNum=307999372  # endTimeBlockNum
                                       )
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getGivenSBT; Description: " + str(e))

    def getActionsVideoUploaded(self, contractAccount: str, startTime: datetime, endTime: datetime):
        assert isinstance(contractAccount, str), "contractAccount is not of type str"
        assert isinstance(startTime, datetime), "startTime is not of type datetime"
        assert isinstance(endTime, datetime), "endTime is not of type datetime"
        try:
            if startTime > endTime:
                return ResponseError("Start time is after end time")

            startTimeResponse = self.getBlockNumOfTimestamp(timestamp=startTime)
            if isinstance(startTimeResponse, ResponseSuccessful):
                startTimeBlockNum = startTimeResponse.data
            else:
                return ResponseError("Could not get block number of start time:" + str(startTime))

            endTimeResponse = self.getBlockNumOfTimestamp(timestamp=endTime)
            if isinstance(endTimeResponse, ResponseSuccessful):
                endTimeBlockNum = endTimeResponse.data
            else:
                return ResponseError("Could not get block number of end time:" + str(endTime))

            if isinstance(startTimeBlockNum, int) == False or isinstance(endTimeBlockNum, int) == False:
                return ResponseError("Could not get block number of start time or end time - wrong type")

            graphql: GraphQLApi = GraphQLApi(dfuseConnection=self.dfuseConnection)
            return graphql.getActionsVideoUploaded(account=contractAccount,
                                                   startBlockNum=startTimeBlockNum,
                                                   endBlockNum=endTimeBlockNum)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getActionsVideoUploaded; Description: " + str(e))

    def getActionsInducted(self, contractAccount: str, startTime: datetime, endTime: datetime):
        assert isinstance(contractAccount, str), "contractAccount is not of type str"
        assert isinstance(startTime, datetime), "startTime is not of type datetime"
        assert isinstance(endTime, datetime), "endTime is not of type datetime"
        try:
            if startTime > endTime:
                return ResponseError("Start time is after end time")

            startTimeResponse = self.getBlockNumOfTimestamp(timestamp=startTime)
            if isinstance(startTimeResponse, ResponseSuccessful):
                startTimeBlockNum = startTimeResponse.data
            else:
                return ResponseError("Could not get block number of start time:" + str(startTime))

            endTimeResponse = self.getBlockNumOfTimestamp(timestamp=endTime)
            if isinstance(endTimeResponse, ResponseSuccessful):
                endTimeBlockNum = endTimeResponse.data
            else:
                return ResponseError("Could not get block number of end time:" + str(endTime))

            if isinstance(startTimeBlockNum, int) == False or isinstance(endTimeBlockNum, int) == False:
                return ResponseError("Could not get block number of start time or end time - wrong type")

            graphql: GraphQLApi = GraphQLApi(dfuseConnection=self.dfuseConnection)
            return graphql.getActionsInducted(account=contractAccount,
                                              startBlockNum=startTimeBlockNum,
                                              endBlockNum=endTimeBlockNum)
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getActionsInducted; Description: " + str(e))


    def checkIfGroupSentVideo(self, actionVideoReport: list, round: int, participants: list[Participant]):
        assert isinstance(actionVideoReport, list), "actionVideoReport must be type of list"
        assert isinstance(round, int), "round must be type of int"
        assert isinstance(participants, list), "participants must be type of list"
        try:
            LOG.debug("checkIfGroupSentVideo; Round: " + str(round) + "; Participants: " + str(participants))
            if round < 0:
                LOG.exception("Round must be positive number")
                raise Exception("Round must be positive number")
            if len(participants) == 0:
                LOG.exception("Participants list is empty")
                raise Exception("Participants list is empty")
            for participant in participants:
                if isinstance(participant, Participant) is False:
                    LOG.exception("Participants list must contain only Participant objects")
                    raise Exception("Participants list must contain only Participant objects")

            TRACE = 'trace'
            MATCHING_ACTION = 'matchingActions'
            DATA = 'data'
            ROUND = 'round'
            VOTER = 'voter'

            for action in actionVideoReport:
                if TRACE not in action or MATCHING_ACTION not in action[TRACE]:
                    LOG.error("checkIfGroupSentVideo; Trace not in action: " + str(action))
                    continue
                subactions = action[TRACE][MATCHING_ACTION]
                for subaction in subactions:
                    if DATA not in subaction or \
                            ROUND not in subaction[DATA] or \
                            VOTER not in subaction[DATA]:
                        LOG.error("checkIfGroupSentVideo; Data not in subaction: " + str(subaction))
                        continue
                    roundInSubaction = subaction[DATA][ROUND]
                    voterInSubaction = subaction[DATA][VOTER]
                    if roundInSubaction == round:
                        if any(voterInSubaction == participant.telegramID for participant in participants):
                            return True
            return False
        except Exception as e:
            LOG.exception("Error in AfterElectionReminderManagement.checkIfGroupSentVideo: " + str(e))
            raise Exception("Error in AfterElectionReminderManagement.checkIfGroupSentVideo: " + str(e))

    def SBTParser(self, sbtReport: list) -> list[CommunityParticipantDB]:
        assert isinstance(sbtReport, list), "sbtReport must be type of dict"
        try:
            LOG.debug("SBTRowParser")
            TRACE = 'trace'
            MATCHING_ACTION = 'matchingActions'
            CREATED_ACTION = 'createdActions'
            DATA = 'data'

            toReturn: list[CommunityParticipantDB] = []

            for action in sbtReport:
                if TRACE not in action or MATCHING_ACTION not in action[TRACE]:
                    LOG.error("SBT parser; Trace not in action: " + str(action))
                    continue
                matchingActions = action[TRACE][MATCHING_ACTION]
                for matchingAction in matchingActions:
                    if CREATED_ACTION not in matchingAction:
                        LOG.error("SBT parser; Created action not in matching action: " + str(matchingAction))
                        continue

                    createdActions = matchingAction[CREATED_ACTION]
                    for createdAction in createdActions:
                        try:
                            data = createdAction[DATA]

                            pattern = r'round (\d+), (\d+)'

                            match = re.search(pattern, data['memo'])
                            if match:
                                roundIndex = int(match.group(1))
                                unixTimestamp: int = int(match.group(2))
                                timestamp = datetime.fromtimestamp(unixTimestamp)

                                participant: CommunityParticipantDB = CommunityParticipantDB.justSBT(
                                    accountName=data["to"],
                                    sbt=SBT(round=roundIndex, received=timestamp))

                                LOG.success(
                                    "Account: " + str(participant.accountName) + "; SBT: " + str(participant.sbt))
                                # LOG.debug("Parsed community participant: " + str(participant))
                                toReturn.append(participant)
                            else:
                                print("No match!!")
                        except Exception as e:
                            LOG.exception("Error Eden.SBTParser.inline; Description: " + str(e))
            return toReturn
        except Exception as e:
            LOG.exception(str(e))
            raise Exception("Exception thrown when called SBTParser; Description: " + str(e))
            return None

    def actionInductedParser(self, report: list) -> list[CommunityParticipantDB]:
        assert isinstance(report, list), "report must be type of dict"
        try:
            LOG.debug("SBTRowParser")
            TRACE = 'trace'
            MATCHING_ACTION = 'matchingActions'
            CREATED_ACTION = 'createdActions'
            DATA = 'data'
            INDUCTEE= 'inductee'

            toReturn: list[str] = []

            for action in report:
                if TRACE not in action or MATCHING_ACTION not in action[TRACE]:
                    LOG.error("SBT parser; Trace not in action: " + str(action))
                    continue
                matchingActions = action[TRACE][MATCHING_ACTION]
                for matchingAction in matchingActions:
                    if DATA not in matchingAction:
                        LOG.error("SBT parser; Created action not in matching action: " + str(matchingAction))
                        continue
                    data = matchingAction[DATA]
                    if INDUCTEE not in data:
                        LOG.error("SBT parser; INDUCTEE not in matching action: " + str(matchingAction))
                        continue
                    LOG.success("Inducted profile found: " + str(data[INDUCTEE]))
                    inductee: str = data[INDUCTEE]
                    toReturn.append(inductee)
            return toReturn
        except Exception as e:
            LOG.exception(str(e))
            raise Exception("Exception thrown when called actionInductedParser; Description: " + str(e))
            return None


def main():
    print("Hello World!")


if __name__ == "__main__":
    main()
