import threading
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


class EdenBot1:
    botMode: EdenBotMode

    def __init__(self, telegramApiID: int, telegramApiHash: str, botToken: str, database: Database,
                ):
        LOG.info("Initialization of EdenBot")
        assert isinstance(telegramApiID, int), "telegramApiID is not an integer"
        assert isinstance(telegramApiHash, str), "telegramApiHash is not a string"
        assert isinstance(botToken, str), "botToken is not a string"
        assert isinstance(database, Database), "database is not an instance of Database"

        self.database = database

        # fill database with election status data if table is empty
        #self.database.fillElectionStatuses()

        self.communication = Communication(database=database)

        #self.communication.startCommAsyncSession(apiId=telegramApiID, apiHash=telegramApiHash, botToken=botToken)

        self.communication.startSessionAsync(apiId=telegramApiID,
                                            apiHash=telegramApiHash,
                                            botToken=botToken)

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

            receivedData = edenData.data

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



def main():
    print("------>Python<-------")
    import sys
    print("\nVersion: " + str(sys.version))
    print("\n\n")
    print("------>EdenBot Support<-------\n\n")

    database = Database()
    dfuseConnection = DfuseConnection(dfuseApiKey=dfuse_api_key, database=database)

    EdenBot1(telegramApiID=telegram_api_id,
             telegramApiHash=telegram_api_hash,
             botToken=telegram_bot_token,
             database=database).start()

    while True:
        time.sleep(1)

    breakpoint = True





if __name__ == "__main__":
    main()
