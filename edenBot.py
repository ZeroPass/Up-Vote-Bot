import asyncio
import time

import datetime as datetime

from chain import EdenData
from chain.dfuse import *
from chain.electionStateObjects import EdenBotMode, CurrentElectionStateHandlerRegistratrionV1, \
    CurrentElectionStateHandlerSeedingV1, CurrentElectionStateHandlerInitVotersV1, CurrentElectionStateHandlerActive, \
    CurrentElectionStateHandlerFinal, CurrentElectionStateHandler
from chain.stateElectionState import ElectCurrTable
from constants import dfuse_api_key, telegram_api_id, telegram_api_hash, telegram_bot_token, CurrentElectionState, \
    eden_account, telegram_user_bot_name, telegram_bot_name
from database import Database, Election, ElectionStatus, Reminder
from database.election import ElectionRound
from log import Log
from datetime import datetime, timedelta
from debugMode.modeDemo import ModeDemo, Mode
from groupManagement import GroupManagement

from random import *

from transmission import Communication, SessionType

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
        try:
            LOG.info("Initialization of EdenBot")
            assert isinstance(edenData, EdenData), "edenData is not an instance of EdenData"
            assert isinstance(telegramApiID, int), "telegramApiID is not an integer"
            assert isinstance(telegramApiHash, str), "telegramApiHash is not a string"
            assert isinstance(botToken, str), "botToken is not a string"
            assert isinstance(database, Database), "database is not an instance of Database"
            assert isinstance(mode, Mode), "mode is not an instance of Mode"
            assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo is not an instance of ModeDemo or None"

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

            # create communication object
            LOG.debug("Initialization of telegram bot...")
            self.communication = Communication(database=database)

            # to run callback part of pyrogram library on separated thread - not as separated executable file
            self.communication.startCommAsyncSession(apiId=telegramApiID, apiHash=telegramApiHash, botToken=botToken)

            self.communication.startComm(apiId=telegramApiID,
                                         apiHash=telegramApiHash,
                                         botToken=botToken)

            LOG.debug("Creating first communication session user bot to bot if not yet created")
            self.sayHelloFromUserBotToBot(userBotUsername=telegram_user_bot_name,
                                          botUsername=telegram_bot_name)

            LOG.debug(" ...and group management object ...")
            self.groupManagement = GroupManagement(edenData=edenData,
                                                   database=self.database,
                                                   communication=self.communication,
                                                   mode=mode)

            LOG.debug("... is finished")

            # set current election state
            self.currentElectionStateHandler: CurrentElectionStateHandler = None
            self.setCurrentElectionStateAndCallCustomActions(contract=eden_account, database=self.database)
        except Exception as e:
            LOG.exception("Exception in EdenBot.init. Description: " + str(e))

    def sayHelloFromUserBotToBot(self, userBotUsername: str, botUsername: str):
        try:
            self.communication.updateKnownUserData(botName=botUsername)

            if self.communication.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=botUsername,
                                                                                  telegramID=str(userBotUsername)) \
                    is False:
                response: bool= self.communication.sendMessage(sessionType=SessionType.USER,
                                               chatId=str(botUsername),
                                               text="/start")

                if response:
                    LOG.success("EdenBot.sayHelloFromUserBotToBot; Message sent to bot")
                else:
                    LOG.error("EdenBot.sayHelloFromUserBotToBot; Message not sent to bot")


        except Exception as e:
            LOG.exception("Exception in EdenBot.sayHelloFromUserBotToBot. Description: " + str(e))

    def manageElectionInDB(self, electionsStateStr: str, data: dict, contract: str, database: Database) -> Election:
        assert isinstance(electionsStateStr, str), "electionsStateStr is not a string"
        assert isinstance(data, dict), "data is not a dict"
        assert isinstance(contract, str), "contract is not a string"
        assert isinstance(database, Database), "database is not an instance of Database"
        try:
            electionState = electionsStateStr
            election: Election = None
            electionStatusIDfromDB = None
            if electionState == "current_election_state_registration_v1":
                self.currentElectionStateHandler = CurrentElectionStateHandlerRegistratrionV1(data)
                # get election state from the database
                electionStatusIDfromDB: ElectionStatus = \
                    database.getElectionStatus(self.currentElectionStateHandler.currentElectionState)
                if electionStatusIDfromDB == None:
                    LOG.exception("EdenBot.manageElectionInDB; 'Election status' not found in database")
                    raise Exception("EdenBot.manageElectionInDB; 'Election status' not found in database")
                # set election data to save in the database
                election: Election = Election(date=datetime.fromisoformat(
                    self.currentElectionStateHandler.getStartTime()),
                    status=electionStatusIDfromDB,
                    contract=contract)

            elif electionState == "current_election_state_seeding_v1":
                self.currentElectionStateHandler = CurrentElectionStateHandlerSeedingV1(data)
                # get election state from the database
                electionStatusIDfromDB: ElectionStatus = \
                    database.getElectionStatus(self.currentElectionStateHandler.currentElectionState)
                if electionStatusIDfromDB == None:
                    LOG.exception("EdenBot.manageElectionInDB; 'Election status' not found in database")
                    raise Exception("EdenBot.manageElectionInDB; 'Election status' not found in database")
                # set election data to save in the database
                election: Election = Election(date=datetime.fromisoformat(
                    self.currentElectionStateHandler.getSeedEndTime()),
                    status=electionStatusIDfromDB,
                    contract=contract)

            elif electionState == "current_election_state_init_voters_v1":
                self.currentElectionStateHandler = CurrentElectionStateHandlerInitVotersV1(data)
            elif electionState == "current_election_state_active":
                self.currentElectionStateHandler = CurrentElectionStateHandlerActive(data)
            elif electionState == "current_election_state_final":
                self.currentElectionStateHandler = CurrentElectionStateHandlerFinal(data)
            else:
                raise EdenBotException("Unknown current election state: " + str(electionState))

            if election is not None:
                LOG.debug("Pre-election state: " + str(election))
                LOG.info("Save election to database ( +creating reminders) : " + str(election))

                if electionStatusIDfromDB is None:
                    LOG.exception("EdenBot.manageElectionInDB; 'Election status' is None")
                    raise Exception("EdenBot.manageElectionInDB; 'Election status' is None")

                # setting new election + creating notification records
                election = database.setElection(election=election, electionStatus=electionStatusIDfromDB)
                database.createRemindersIfNotExists(election=election)

                # create (if not exists) dummy elections for storing free room data
                database.createElectionForFreeRoomsIfNotExists(contract=contract, election=election)
            else:
                LOG.info("Election is in progress. Get it from database...")
                election = database.getLastElection(contract=contract)

            if election is None:
                raise EdenBotException("EdenBot.manageElectionInDB: Election is None.")

            #########################
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

            # election state is active and changed
            if self.currentElectionStateHandler.getIsInLive():
                if isinstance(self.currentElectionStateHandler, CurrentElectionStateHandlerActive):
                    currentRound: int = self.currentElectionStateHandler.getRound()
                else:
                    #election state final
                    currentRound: int = ElectionRound.FINAL.value
                previousRound: int = database.updateElectionRoundLive(election=election, currentRound=currentRound)
                if previousRound is not None and previousRound != currentRound:
                    #if round changed - set flag ; there will be functions that are called only when round is changed
                    LOG.debug("Current round is changed from " + str(previousRound) + " to: " + str(currentRound))
                    self.currentElectionStateHandler.setIsRoundChanged(isChanged=True,
                                                                       round=previousRound)
                    # update election round in live object
                    election.roundLive = currentRound
                else:
                    LOG.debug("Current round is not changed")
                    self.currentElectionStateHandler.setIsRoundChanged(isChanged=False)


            ##########################

            # return current election state
            return election

        except Exception as e:
            LOG.exception("Exception in manageElectionInDB. Description: " + str(e))
            return None

    def getElectionState(self) -> ElectCurrTable:
        try:
            edenData: Response = self.edenData.getElectionState(height=self.modeDemo.currentBlockHeight if \
                self.modeDemo is not None else None)

            if isinstance(edenData, ResponseError):
                raise EdenBotException("Error when called eden.getElectionState; Description: " + edenData.error)
            if isinstance(edenData.data, ResponseError):
                raise EdenBotException("Error when called eden.getElectionState; Description: " + edenData.data.error)

            receivedData = edenData.data
            electCurrTable: ElectCurrTable = ElectCurrTable(receivedData)

            if electCurrTable.type != "election_state_v0":
                raise EdenBotException("Unknown election state type: " + str(electCurrTable.type))

            return electCurrTable
        except Exception as e:
            LOG.exception("Exception in getElectionState. Description: " + str(e))
            return None

    def setCurrentElectionStateAndCallCustomActions(self, contract: str, database: Database):
        try:
            assert isinstance(contract, str), "contract is not a string"
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

            receivedData = edenData.data

            # initialize state, create election(+dummy elections) and create notification rows in database
            election: Election = self.manageElectionInDB(electionsStateStr=receivedData[0],
                                                         data=receivedData[1],
                                                         contract=contract,
                                                         database=database)

            if election is None:
                LOG.exception("EdenBot.setCurrentElectionStateAndCallCustomActions; 'Election' is None")
                raise Exception("EdenBot.setCurrentElectionStateAndCallCustomActions; 'Election' is None")

            # get current election state to manage business logic
            currentElectionState = self.currentElectionStateHandler.currentElectionState

            if currentElectionState == CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V1:
                electionCurrState: ElectCurrTable = self.getElectionState()
                self.currentElectionStateHandler.customActions(election=election,
                                                               electCurr=electionCurrState,
                                                               database=database,
                                                               groupManagement=self.groupManagement,
                                                               edenData=self.edenData,
                                                               communication=self.communication,
                                                               modeDemo=self.modeDemo)
            elif currentElectionState == CurrentElectionState.CURRENT_ELECTION_STATE_SEEDING_V1:
                self.currentElectionStateHandler.customActions(election=election,
                                                               database=database,
                                                               groupManagement=self.groupManagement,
                                                               edenData=self.edenData,
                                                               communication=self.communication,
                                                               modeDemo=self.modeDemo)
            elif currentElectionState == CurrentElectionState.CURRENT_ELECTION_STATE_INIT_VOTERS_V1:
                self.currentElectionStateHandler.customActions()
            elif currentElectionState == CurrentElectionState.CURRENT_ELECTION_STATE_ACTIVE:
                self.currentElectionStateHandler.customActions(election=election,
                                                               groupManagement=self.groupManagement,
                                                               database=database,
                                                               edenData=self.edenData,
                                                               communication=self.communication,
                                                               modeDemo=self.modeDemo)
            elif currentElectionState == CurrentElectionState.CURRENT_ELECTION_STATE_FINAL:
                self.currentElectionStateHandler.customActions(election=election,
                                                               groupManagement=self.groupManagement,
                                                               modeDemo=self.modeDemo)
            else:
                raise EdenBotException("Unknown current election state: " + str(receivedData[0]))

            LOG.debug("Current election state: " + str(receivedData[0]) + " with data: ".join(
                ['{0}= {1}'.format(k, v) for k, v in receivedData[1].items()]))

            if election is None:
                raise EdenBotException("Election is still None - not set in database")
        except Exception as e:
            LOG.exception("Exception in setCurrentElectionStateAndCallCustomActions. Description: " + str(e))

    def start(self):
        LOG.info("Starting EdenBot")
        try:
            i = 0
            while True:

                # self.edenData.updateDfuseApiKey2(self.database) #just test

                # sleep time depends on bot mode
                if self.mode == Mode.LIVE:
                    time.sleep(REPEAT_TIME[self.currentElectionStateHandler.edenBotMode])

                elif self.mode == Mode.DEMO and self.modeDemo is not None:
                    # Mode.DEMO
                    LOG.debug("Demo mode: sleep time: " + str(10))
                    time.sleep(10)  # in demo mode sleep 3

                    if self.modeDemo.isLiveMode():
                        self.modeDemo.setNextLiveBlockAndTimestamp()

                    else:
                        if self.modeDemo.isNextTimestampInLimit(seconds=60):
                            self.modeDemo.setNextTimestamp(seconds=60)
                        else:
                            LOG.success("Time limit reached - Demo mode finished")
                            break

                else:
                    raise EdenBotException("Unknown Mode(LIVE, DEMO) or Mode.Demo and ModeDemo is None ")

                # defines current election state and write it to the database
                self.setCurrentElectionStateAndCallCustomActions(contract=eden_account, database=self.database)

        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise EdenBotException("Exception: " + str(e))


def main():
    print("------>Python<-------")
    import sys
    print("\nVersion: " + str(sys.version))
    print("\n\n")
    print("------>EdenBot<-------\n\n")
    database = Database()
    dfuseConnection = DfuseConnection(dfuseApiKey=dfuse_api_key, database=database)

    edenData: EdenData = EdenData(dfuseConnection=dfuseConnection)

    startEndDatetimeList = [
        #(datetime(2022, 10, 7, 11, 52), datetime(2022, 10, 7, 11, 59)),  # add user
        #(datetime(2022, 10, 7, 12, 0), datetime(2022, 10, 7, 12, 2)),  # notification 25 hours before
        #(datetime(2022, 10, 7, 12, 57), datetime(2022, 10, 7, 12, 58)),  # adding users
        #(datetime(2022, 10, 7, 12, 59), datetime(2022, 10, 7, 13, 2)),  # notification - 24 hoavtomat picaurs before
        #(datetime(2022, 10, 8, 11, 58), datetime(2022, 10, 8, 12, 2)),  # notification - in one hour
        #(datetime(2022, 10, 8, 12, 57), datetime(2022, 10, 8, 12, 59)),  # notification - in few minutes
        #(datetime(2022, 10, 8, 12, 59), datetime(2022, 10, 8, 13, 2)),  # start
        #(datetime(2022, 10, 8, 13, 51), datetime(2022, 10, 8, 13, 58)),  # notification  10 and 5 min left
        #(datetime(2022, 10, 8, 13, 59), datetime(2022, 10, 8, 14, 3)),  # round 1 finished, start round 2
        #(datetime(2022, 10, 8, 14, 51), datetime(2022, 10, 8, 14, 58)),  # notification  10 and 5 min left
        #(datetime(2022, 10, 8, 14, 59), datetime(2022, 10, 8, 15, 3)),  # round 2 finished, start final round
        (datetime(2022, 10, 15, 13, 0), datetime(2022, 10, 15, 13, 1)),  # one week before video deadline
        (datetime(2022, 10, 20, 13, 0), datetime(2022, 10, 20, 13, 1)),  # two days before video deadline
        (datetime(2022, 10, 21, 13, 0), datetime(2022, 10, 21, 13, 1)),  # one day before video deadline

        #elections 6
        #(datetime(2023, 4, 8, 13, 5), datetime(2023, 4, 8, 13, 6)),  # round 1
        #(datetime(2023, 4, 8, 17, 15), datetime(2023, 4, 8, 17, 18)),  # after elections
    ]

    # 120 blocks per minute
    #modeDemo = ModeDemo(startAndEndDatetime=startEndDatetimeList,
    #                    edenObj=edenData,
    #                    step=1  # 1.5 min
    #                    )
    # live!
    modeDemo = ModeDemo.live(edenObj=edenData,
                             stepBack=10)

    EdenBot(edenData=edenData,
            telegramApiID=telegram_api_id,
            telegramApiHash=telegram_api_hash,
            botToken=telegram_bot_token,
            mode=Mode.DEMO,
            database=database,
            modeDemo=modeDemo).start()

    while True:
        time.sleep(1)

    breakpoint = True


def runPyrogramTestMode(comm: Communication):
    # database = Database()
    # comm = Communication(database=database)
    comm.idle()


def mainPyrogramTestMode():
    # multiprocessing
    database = Database()
    comm = Communication(database=database)
    comm.startComm(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)

    comm.sendMessage(sessionType=SessionType.BOT,
                     chatId="",
                     text="test")

    # comm.sendMessage(chatId="", sessionType=SessionType.BOT, text="te423423st")
    # comm.sendMessage(chatId='-1001776498331', sessionType=SessionType.BOT, text="test")
    pyogram = Process(target=runPyrogramTestMode, args=(comm,))
    pyogram.start()

    i = 0
    while True:
        i = i + 1
        # if i % 3 == 0:
        if i == 3:
            comm.sendMessage(chatId="", sessionType=SessionType.BOT, text="test")
        time.sleep(3)
        print("main Thread")


def main1():
    database = Database()
    election: Election = Election(electionID=10,
                                  status=ElectionStatus(electionStatusID=7,
                                                        status=CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V0),
                                  date=datetime.now(),
                                  contract=eden_account
                                  )

    #kva = database.getMembers(election=election)
    #kva1 = kva.Room
    #kva2 = kva.Participant

    #reminder: Reminder = Reminder(reminderID=8, electionID=2, dateTimeBefore=datetime.now(), round=0)
    #test = database.electionGroupsCreated(election=election, round=0, numRooms=20)

    kva = 8

    comm = Communication(database=database)
    comm.startComm(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    comm.sendMessage(chatId=-1001888934788, sessionType=SessionType.BOT, text="test")
    #neki = await comm.isVideoCallRunning(sessionType=SessionType.BOT, chatId=-1001888934788)
    task = asyncio.get_event_loop().run_until_complete(comm.isVideoCallRunning(sessionType=SessionType.BOT,
                                                                               chatId=-1001888934788))
    kva =- 8

    while True:
        time.sleep(2)


if __name__ == "__main__":
    main()
    #main1()
    # mainPyrogramTestMode() #to test pyrogram application - because of one genuine session file
