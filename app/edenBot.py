from enum import Enum

import time

from app.chain import EdenData
from app.chain.dfuse import *
from app.chain.electionStateObjects import EdenBotMode, CurrentElectionStateHandlerRegistratrionV1, \
    CurrentElectionStateHandlerSeedingV1, CurrentElectionStateHandlerInitVotersV1, CurrentElectionStateHandlerActive, \
    CurrentElectionStateHandlerFinal, CurrentElectionStateHandler
from app.constants import dfuse_api_key, telegram_api_id, telegram_api_hash, telegram_bot_token, CurrentElectionState
from app.database import Database, Election
from app.log import Log
from datetime import datetime, timedelta
from app.debugMode.modeDemo import ModeDemo, Mode
from app.groupManagement import GroupManagement
import gettext

from app.transmission import Communication, SessionType

from multiprocessing import Process


class EdenBotException(Exception):
    pass


LOG = Log(className="EdenBot")

REPEAT_TIME = {
    EdenBotMode.ELECTION: 45,  # every 45 seconds
    EdenBotMode.NOT_ELECTION: 60 * 10  # every half hour 60 seconds  x 10 minutes
}


class EdenBot:
    botMode: EdenBotMode

    def __init__(self, edenData: EdenData, telegramApiID: int, telegramApiHash: str, botToken: str, database: Database,
                 mode: Mode, modeDemo: ModeDemo = None):
        LOG.info("Initialization of EdenBot")
        assert isinstance(edenData, EdenData), "edenData is not an instance of EdenData"
        assert isinstance(telegramApiID, int), "telegramApiID is not an integer"
        assert isinstance(telegramApiHash, str), "telegramApiHash is not a string"
        assert isinstance(botToken, str), "botToken is not a string"
        assert isinstance(database, Database), "database is not an instance of Database"

        self.database = database

        # fill database with election status data if table is empty
        self.database.fillElectionStatuses()

        self.mode = mode
        self.modeDemo = modeDemo
        # if demo mode is set, then 'modeDemo' must be set
        if mode == Mode.DEMO:
            assert modeDemo is not None
        self.edenData = edenData

        if mode == Mode.DEMO and False:
            responseStart: Response = self.edenData.getBlockNumOfTimestamp(modeDemo.getStart())
            responseEnd: Response = self.edenData.getBlockNumOfTimestamp(modeDemo.getEnd())
            if isinstance(responseStart, ResponseError) or isinstance(responseEnd, ResponseError):
                LOG.exception("Error when called getBlockNumOfTimestamp; Description: " + responseStart.error)
                raise EdenBotException("Error when called getBlockNumOfTimestamp. Raise exception")

            self.modeDemo.setStartBlockHeight(responseStart.data)  # set start block height
            self.modeDemo.setEndBlockHeight(responseEnd.data)  # set end block height

        # difference between server and node time
        self.timeDiff = self.edenData.getDifferenceBetweenNodeAndServerTime(serverTime=datetime.now(),
                                                                            nodeTime=self.edenData.getChainDatetime())

        # creat communication object
        LOG.debug("Initialization of telegram bot...")
        self.communication = Communication(database=database)
        self.communication.start(apiId=telegramApiID,
                                 apiHash=telegramApiHash,
                                 botToken=botToken)

        LOG.debug(" ...and group management object ...")
        self.groupManagement = GroupManagement(edenData=edenData,
                                               database=self.database,
                                               communication=self.communication,
                                               mode=mode)

        LOG.debug("... is finished")

        # set current election state
        self.currentElectionStateHandler: CurrentElectionStateHandler = None
        self.setCurrentElectionStateAndCallCustomActions(database=self.database)

    def setCurrentElectionStateAndCallCustomActions(self, database: Database):
        try:
            assert isinstance(database, Database), "database is not an instance of Database"
            LOG.debug("Check current election state from blockchain on height: " + str(
                self.modeDemo.getCurrentBlock()) if self.modeDemo is not None else "<current/live>")
            edenData: Response = self.edenData.getCurrentElectionState(height=self.modeDemo.currentBlockHeight
            if self.modeDemo is not None else None)
            if isinstance(edenData, ResponseError):
                raise EdenBotException(
                    "Error when called eden.getCurrentElectionState; Description: " + edenData.error)
            if isinstance(edenData.data, ResponseError):
                raise EdenBotException(
                    "Error when called eden.getCurrentElectionState; Description: " + edenData.data.error)

            receivedData = edenData.data.data

            election: Election = None
            # initialize state and call custom action if exists, otherwise there is just a comment in log
            electionState = receivedData[0]
            if electionState == "current_election_state_registration_v1":
                self.currentElectionStateHandler = CurrentElectionStateHandlerRegistratrionV1(receivedData[1])
                self.currentElectionStateHandler.customActions(database=database,
                                                               edenData=self.edenData,
                                                               communication=self.communication,
                                                               modeDemo=self.modeDemo)
            elif electionState == "current_election_state_seeding_v1":
                self.currentElectionStateHandler = CurrentElectionStateHandlerSeedingV1(receivedData[1])
                self.currentElectionStateHandler.customActions(database=database,
                                                               edenData=self.edenData,
                                                               communication=self.communication,
                                                               modeDemo=self.modeDemo)
            elif electionState == "current_election_state_init_voters_v1":
                self.currentElectionStateHandler = CurrentElectionStateHandlerInitVotersV1(receivedData[1])
                self.currentElectionStateHandler.customActions()
            elif electionState == "current_election_state_active":
                election = self.database.getLastElection()
                self.currentElectionStateHandler = CurrentElectionStateHandlerActive(receivedData[1])
                self.currentElectionStateHandler.customActions(election=self.database.getLastElection(),
                                                               groupManagement=self.groupManagement,
                                                               database=database,
                                                               edenData=self.edenData,
                                                               communication=self.communication,
                                                               modeDemo=self.modeDemo)
            elif electionState == "current_election_state_final":
                self.currentElectionStateHandler = CurrentElectionStateHandlerFinal(receivedData[1])
                self.currentElectionStateHandler.customActions(groupManagement=self.groupManagement,
                                                               modeDemo=self.modeDemo)
            else:
                raise EdenBotException("Unknown current election state: " + str(receivedData[0]))

            LOG.debug("Current election state: " + str(receivedData[0]) + " with data: ".join(
                ['{0}= {1}'.format(k, v) for k, v in receivedData[1].items()]))

            if election is None:
                election = self.database.getLastElection()
                if election is None:
                    raise EdenBotException("Election is still None - not set in database")

            # write current election state to database
            previousElectionState: CurrentElectionState = \
                database.updateElectionColumnElectionStateIfChanged(election=election,
                                                                    currentElectionState=
                                                                    self.currentElectionStateHandler.
                                                                    currentElectionState)
            if previousElectionState is not None:
                LOG.debug("Previous election state: " + str(previousElectionState.value) + " changed to: "
                      + str(self.currentElectionStateHandler.currentElectionState.value))
            else:
                LOG.debug("Election state is not changed")
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise EdenBotException("Exception: " + str(e))

    def start(self):
        LOG.info("Starting EdenBot")
        try:
            while True:
                # sleep time depends on bot mode
                if self.mode == Mode.LIVE:
                    time.sleep(REPEAT_TIME[self.currentElectionStateHandler.edenBotMode])

                elif self.mode == Mode.DEMO and self.modeDemo is not None:
                    # Mode.DEMO
                    LOG.debug("Demo mode: sleep time: " + str(0.1))
                    time.sleep(0.1)  # in demo mode sleep 0.1s
                    #REPEAT_TIME[self.currentElectionStateHandler.edenBotMode]
                    if self.modeDemo.isNextTimestampInLimit(seconds=60):
                        self.modeDemo.setNextTimestamp(seconds=60)
                    else:
                        LOG.success("Time limit reached - Demo mode finished")
                        break

                else:
                    raise EdenBotException("Unknown Mode(LIVE, DEMO) or Mode.Demo and ModeDemo is None ")


                # define current election state and write it to the database
                self.setCurrentElectionStateAndCallCustomActions(database=self.database)

        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise EdenBotException("Exception: " + str(e))


def main():
    print("------>Python<-------")
    import sys
    print("\nVersion: " + str(sys.version))
    print("\n\n")
    print("------>EdenBot<-------\n\n")

    dfuseConnection = DfuseConnection(dfuseApiKey=dfuse_api_key)
    database = Database()
    edenData: EdenData = EdenData(dfuseConnection=dfuseConnection, database=database)

    startEndDatetimeList = [
        #####(datetime(2022, 10, 7, 11, 58), datetime(2022, 10, 7, 11, 59)),  # add user
        ####(datetime(2022, 10, 7, 12, 0), datetime(2022, 10, 7, 12, 2)),  # notification 25 hours before
        #(datetime(2022, 10, 7, 12, 58), datetime(2022, 10, 7, 13, 2)),  # notification 24 hours before
        (datetime(2022, 10, 8, 11, 38), datetime(2022, 10, 8, 12, 2)),  # in one hour #TODO chaNGE TO 58
        (datetime(2022, 10, 8, 12, 58), datetime(2022, 10, 8, 13, 4)),  # in few minutes + start
        (datetime(2022, 10, 8, 13, 49), datetime(2022, 10, 8, 13, 58)),  # notification  10 and 5 min left
        (datetime(2022, 10, 8, 13, 59), datetime(2022, 10, 8, 14, 3)),  # round 1 finished, start round 2
        (datetime(2022, 10, 8, 14, 49), datetime(2022, 10, 8, 14, 58)),  # notification  10 and 5 min left
        (datetime(2022, 10, 8, 14, 59), datetime(2022, 10, 8, 15, 3)),  # round 2 finished, start final round
    ]


    #120 blocks per minute
    modeDemo = ModeDemo(startAndEndDatetime=startEndDatetimeList,
                        edenObj=edenData,
                        step=1  # 1.5 min
                        )


    EdenBot(edenData=edenData,
            telegramApiID=telegram_api_id,
            telegramApiHash=telegram_api_hash,
            botToken=telegram_bot_token,
            mode=Mode.DEMO,
            database=database,
            modeDemo=modeDemo).start()

    breakpoint = True


def runPyrogramTestMode():
    comm = Communication()
    comm.start(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    comm.idle()

def mainPyrogramTestMode():
    # multiprocessing
    pyogram = Process(target=runPyrogramTestMode)
    pyogram.start()

    counter = 0
    while True:
        time.sleep(3)
        counter += 1
        if counter > 10:
            pyrogram.
        print("main Thread")

if __name__ == "__main__":
    #import requests
    #token = "tkn"
    #params = {"limit": 100,
    #          "allowed_updates": ["my_chat_member"]}
    #r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params).json()

    #for i in range(0, len(r["result"])):
    #    if not r["result"][i]["message"]["from"]["id"] in users:
    #        users.append(r["result"][i]["message"]["from"]["id"])



    main()
    #mainPyrogramTestMode() #to test pyrogram application - because of one genuine session file
