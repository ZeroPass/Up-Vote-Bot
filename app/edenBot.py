from enum import Enum

import chain
import database
import transmission
import time

from app.chain import EdenData
from app.chain.dfuse import *
from app.chain.electionStateObjects import EdenBotMode, CurrentElectionStateHandlerRegistratrionV1, \
    CurrentElectionStateHandlerSeedingV1, CurrentElectionStateHandlerInitVotersV1, CurrentElectionStateHandlerActive, \
    CurrentElectionStateHandlerFinal, CurrentElectionStateHandler
from app.constants import dfuse_api_key, telegram_api_id, telegram_api_hash, telegram_bot_token
from app.database import Database
from app.log import Log
from datetime import datetime
from app.debugMode.modeDemo import ModeDemo, Mode
import gettext

from app.transmission import Communication


######## Multilanguage support in the future -= not translated yet =-
# cn = gettext.translation('base', localedir='locales', languages=['cn'])
# cn.install()
# _ = cn.gettext # Chinese


class EdenBotException(Exception):
    pass


LOG = Log(className="EdenBot")

REPEAT_TIME = {
    EdenBotMode.ELECTION: 10,  # every 10 seconds
    EdenBotMode.NOT_ELECTION: 60 * 60  # every hour
}


class EdenBot:
    botMode: EdenBotMode

    def __init__(self, dfuseApiKey: str, telegramApiID: int, telegramApiHash: str, botToken: str,  mode: Mode, modeDemo: ModeDemo = None):
        LOG.info("Initialization of EdenBot")
        assert isinstance(dfuseApiKey, str), "dfuseApiKey is not a string"
        assert isinstance(telegramApiID, int), "telegramApiID is not an integer"
        assert isinstance(telegramApiHash, str), "telegramApiHash is not a string"
        assert isinstance(botToken, str), "botToken is not a string"



        # fill database with election status data if table is empty
        database: Database = Database()
        database.fillElectionStatuses()

        self.mode = mode
        self.modeDemo = modeDemo
        # if demo mode is set, then 'modeDemo' must be set
        if mode == Mode.DEMO:
            assert modeDemo is not None
        self.edenData = EdenData(dfuseApiKey=dfuseApiKey)

        if mode == Mode.DEMO:
            self.modeDemo.setStartBlockHeight(
                self.edenData.getBlockNumOfTimestamp(modeDemo.getStart()).data)  # set start block height
            self.modeDemo.setEndBlockHeight(
                self.edenData.getBlockNumOfTimestamp(modeDemo.getEnd()).data)  # set end block height

        # difference between server and node time
        self.timeDiff = self.edenData.getDifferenceBetweenNodeAndServerTime(serverTime=datetime.now(),
                                                                            nodeTime=self.edenData.getChainDatetime())

        # creat communication object
        LOG.debug("Initialization of telegram bot...")
        self.communication = Communication()
        self.communication.start(apiId=telegramApiID,
                                 apiHash=telegramApiHash,
                                 botToken=botToken)

        LOG.debug("... is finished")

        # set current election state
        self.currentElectionState: CurrentElectionStateHandler = None
        self.setCurrentElectionStateAndCallCustomActions()



    def getChainHeight(self) -> int:
        if self.mode == Mode.DEMO:
            return self.modeDemo.getCurrentBlock()
        else:
            return None  # live mode

    def botModeElection(self):
        implement = 1

    def botModeNotElection(self):
        # setting up database (participants)
        # sending alerts
        assert (self.currentElectionState is not None), "Current election state is not set"
        if self.currentElectionState == CurrentElectionStateHandlerRegistratrionV1:
            todo = 7

    def setCurrentElectionStateAndCallCustomActions(self):
        try:
            LOG.debug("Check current election state from blockchain on height: " + str(
                self.modeDemo.getCurrentBlock()) if self.modeDemo is not None else "<current/live>")
            edenData: Response = self.edenData.getCurrentElectionState(height=self.modeDemo.currentBlockHeight
            if self.modeDemo is not None else None)
            if isinstance(edenData, ResponseError):
                raise EdenBotException(
                    "Error when called setCurrentElectionStateAndCallCustomActions; Description: " + edenData.error)
            if isinstance(edenData.data, ResponseError):
                raise EdenBotException(
                    "Error when called setCurrentElectionStateAndCallCustomActions; Description: " + edenData.data.error)

            receivedData = edenData.data.data

            # initialize state and call custom action if exists, motherwise there is just a comment in log
            electionState = receivedData[0]
            if electionState == "current_election_state_registration_v1":
                self.currentElectionState = CurrentElectionStateHandlerRegistratrionV1(receivedData[1])
                self.currentElectionState.customActions(communication=self.communication,
                                                        modeDemo=self.modeDemo)
            elif electionState == "current_election_state_seeding_v1":
                self.currentElectionState = CurrentElectionStateHandlerSeedingV1(receivedData[1])
                self.currentElectionState.customActions(communication=self.communication,
                                                        modeDemo=self.modeDemo)
            elif electionState == "current_election_state_init_voters_v1":
                self.currentElectionState = CurrentElectionStateHandlerInitVotersV1(receivedData[1])
                self.currentElectionState.customActions()
            elif electionState == "current_election_state_active":
                self.currentElectionState = CurrentElectionStateHandlerActive(receivedData[1])
                self.currentElectionState.customActions()
            elif electionState == "current_election_state_final":
                self.currentElectionState = CurrentElectionStateHandlerFinal(receivedData[1])
                self.currentElectionState.customActions()
            else:
                raise EdenBotException("Unknown current election state: " + str(receivedData[0]))

            LOG.debug("Current election state: " + str(receivedData[0]) + " with data: ".join(
                ['{0}={1}'.format(k, v) for k, v in receivedData[1].items()]))
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise EdenBotException("Exception: " + str(e))

    def sendAlert(self):
        LOG.info("Send alert")
        try:
            # TODO: implement
            r = 9
            # self.edenData.sendAlert()
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise EdenBotException("Exception: " + str(e))

    def start(self):
        LOG.info("Starting EdenBot")
        try:
            # init database
            database = Database()

            while True:
                # sleep time depends on bot mode
                if self.mode == Mode.LIVE:
                    time.sleep(REPEAT_TIME[self.currentElectionState.edenBotMode].value)
                else:
                    # Mode.DEMO
                    time.sleep(0.1)  # in demo mode sleep 0.1s

                # increase chain height if DEMO mode
                if self.mode == Mode.DEMO:
                    if self.modeDemo.isNextBlock():
                        blockHeihgt: int = self.modeDemo.getNextBlock()
                        LOG.info("Next block height (DEMO mode): " + str(blockHeihgt))
                    else:
                        LOG.debug("No next block height (DEMO mode);")
                        LOG.success("Demo mode finished")
                        break

                # define current election state
                self.setCurrentElectionStateAndCallCustomActions()

                # check if there is a time for telegram alert message

                # call the function that corresponds to the bot mode
                if self.currentElectionState.getBotMode() == EdenBotMode.ELECTION:
                    LOG.info("ELECTION")
                    self.botModeElection()
                else:
                    LOG.info("NOT_ELECTION")
                    self.botModeNotElection()

        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise EdenBotException("Exception: " + str(e))


def main():
    print("------>EdenBot<-------")
    import sys
    print(sys.version)

    modeDemo = ModeDemo(start=datetime(2022, 7, 9, 11, 59),
                        end=datetime(2022, 7, 9, 13, 30),
                        edenObj=EdenData(dfuseApiKey=dfuse_api_key),
                        step=240  # 2min
                        )
    EdenBot(dfuseApiKey=dfuse_api_key,
            telegramApiID=telegram_api_id,
            telegramApiHash=telegram_api_hash,
            botToken=telegram_bot_token,
            mode=Mode.DEMO, modeDemo=modeDemo).start()

    breakpoint = True


if __name__ == "__main__":
    main()
