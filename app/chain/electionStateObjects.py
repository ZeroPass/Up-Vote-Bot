from enum import Enum

from app.chain import EdenData
from app.constants import dfuse_api_key, pre_created_groups_total, pre_created_groups_created_groups_in_one_round, \
    pre_created_groups_how_often_creating_in_min
from app.dateTimeManagement import DateTimeManagement
from app.debugMode.modeDemo import ModeDemo, Mode
from app.groupManagement import GroupManagement
from app.log import Log
from datetime import datetime, timedelta
from app.constants.electionState import CurrentElectionState

from app.database import Election, Database, ElectionStatus, ExtendedRoom

from app.participantsManagement import ParticipantsManagement
from app.reminderManagement import ReminderManagement
from app.transmission import Communication

LOG = Log(className="CurrentElectionStateHandler")


class EdenBotMode(Enum):
    NOT_ELECTION = 1,
    ELECTION = 2,


class CurrentElectionStateHandler:
    def __init__(self, state: CurrentElectionState, data: dict, edenBotMode: EdenBotMode):
        assert isinstance(state, CurrentElectionState)
        assert isinstance(data, dict)
        assert isinstance(edenBotMode, EdenBotMode)
        self.currentElectionState: CurrentElectionState = state
        self.data: dict = data
        self.edenBotMode: EdenBotMode = edenBotMode

    def getBotMode(self) -> EdenBotMode:
        return self.edenBotMode

    def customActions(self):
        """Override this method to add custom actions"""
        LOG.debug("No custom actions defined")
        pass

    """def sendNotification(self):
        #Check/Send telegram notification in EdenBotMode.NOT_ELECTION
        LOG.debug("Check/Send telegram notification")
        if self.edenBotMode == EdenBotMode.ELECTION:
            return

        database: Database = Database()"""


# Data['current_election_state_registration_v1', {'start_time': '2022-10-08T13:00:00.000', 'election_threshold': 1000, 'election_schedule_version': 1}]
class CurrentElectionStateHandlerRegistratrionV1(CurrentElectionStateHandler):
    def __init__(self, data: dict):
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V1, data, EdenBotMode.NOT_ELECTION)

    def getStartTime(self):
        return self.data["start_time"]

    def getElectionTreshold(self):
        return self.data["election_treshold"]

    def getelectionScheduleVersion(self):
        return self.data["election_schedule_version"]

    def customActions(self, database: Database, edenData: EdenData, communication: Communication,
                      modeDemo: ModeDemo = None):
        LOG.debug("Custom actions for CURRENT_ELECTION_STATE_REGISTRATION_V1")
        LOG.info("Saving election datetime in database")

        electionStatusIDfromDB: ElectionStatus = database.getElectionStatus(self.currentElectionState)
        if electionStatusIDfromDB == None:
            LOG.exception("'Election status' not found in database")
            raise Exception("'Election status' not found in database")

        election: Election = Election(date=datetime.fromisoformat(self.getStartTime()),
                                      status=electionStatusIDfromDB)

        # setting new election + creating notification records
        election = database.setElection(election=election)
        database.createRemindersIfNotExists(election=election)

        # commented for demo only
        # write participants/member in database
        # participantsManagement: ParticipantsManagement = ParticipantsManagement(edenData=edenData, database=database,
        #                                                                        communication=communication)
        # participantsManagement.getParticipantsFromChainAndMatchWithDatabase(election=election,
        #                                                                    height=modeDemo.currentBlockHeight
        #                                                                    if modeDemo is not None else None)

        # create groups before election
        groupManagement: GroupManagement = GroupManagement(edenData=edenData,
                                                           database=database,
                                                           communication=communication,
                                                           modeDemo=modeDemo)
        groupManagement.createPredefinedGroupsIfNeeded(dateTimeManagement=DateTimeManagement(edenData=edenData),
                                                       totalGroups=pre_created_groups_total,
                                                       numberOfGroups=pre_created_groups_created_groups_in_one_round,
                                                       duration=
                                                       timedelta(minutes=pre_created_groups_how_often_creating_in_min)
                                                       )

        # send notification
        reminderManagement: ReminderManagement = ReminderManagement(database=database,
                                                                    edenData=edenData,
                                                                    communication=communication,
                                                                    modeDemo=modeDemo)
        # reminderManagement.createRemindersIfNotExists(election=election) already in setElection
        reminderManagement.sendReminderIfNeeded(election=election,
                                                modeDemo=modeDemo)


# Data['current_election_state_seeding_v1', {'seed': {'current': '0000000000000000000045AB464F6643EC69CBC24B91257A1868DF1684C8DC5C', 'start_time': '2022-07-08T13:00:00.000',
# 'end_time': '2022-07-09T13:00:00.000'}, 'election_schedule_version': 2}]
class CurrentElectionStateHandlerSeedingV1(CurrentElectionStateHandler):
    def __init__(self, data: dict):
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_SEEDING_V1, data,
                         EdenBotMode.ELECTION)  # should be marked as election because of next step

    def getSeed(self):
        return self.data["seed"]

    def getSeedCurrent(self):
        return self.data["seed"]["current"]

    def getSeedStartTime(self):
        return self.data["seed"]["start_time"]

    def getSeedEndTime(self):
        return self.data["seed"]["end_time"]

    def getElectionScheduleVersion(self):
        return self.data["election_schedule_version"]

    def customActions(self, database: Database, edenData: EdenData, communication: Communication,
                      modeDemo: ModeDemo = None):
        LOG.debug("Custom actions for CURRENT_ELECTION_STATE_SEEDING_V1")
        LOG.info("Saving election datetime in database")

        electionStatusIDfromDB: ElectionStatus = database.getElectionStatus(self.currentElectionState)
        if electionStatusIDfromDB == None:
            LOG.exception("'Election status' not found in database")
            raise Exception("'Election status' not found in database")

        election: Election = Election(date=datetime.fromisoformat(self.getSeedEndTime()),
                                      status=electionStatusIDfromDB)

        # setting new election + creating reminder records
        election = database.setElection(election=election)
        database.createRemindersIfNotExists(election=election)

        # write participants/member in database
        # participantsManagement: ParticipantsManagement = ParticipantsManagement(
        #    edenData=EdenData(dfuseApiKey=dfuse_api_key))
        # participantsManagement.getParticipantsFromChainAndMatchWithDatabase(election=election)

        # send notification
        reminderManagement: ReminderManagement = ReminderManagement(database=database,
                                                                    edenData=edenData,
                                                                    communication=communication,
                                                                    modeDemo=modeDemo)
        # reminderManagement.createRemindersIfNotExists(election=election) already in setElection
        reminderManagement.sendReminderIfNeeded(election=election,
                                                modeDemo=modeDemo)


# Data['current_election_state_init_voters_v1', {'next_member_idx': 60, 'rng': {'buf': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 69, 171, 70, 79, 102, 67, 236, 105, 203, 194, 75, 145, 37, 122, 24, 104,
# 223, 22, 132, 200, 220, 92, 11, 0, 0, 0, 0, 0, 0, 0, 9, 85, 162, 164, 162, 194, 3, 246, 27, 242, 40, 209, 36, 104, 250, 250, 114, 23, 166, 132, 170, 103, 243, 159, 202, 22, 143, 219, 18, 115, 133, 216], 'index': 20},
# 'last_processed': 'ncdacventure', 'next_report_index': 0, 'election_schedule_version': 2}]
class CurrentElectionStateHandlerInitVotersV1(CurrentElectionStateHandler):
    def __init__(self, data: dict):
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V1, data, EdenBotMode.NOT_ELECTION)

    def getNextMemberIdx(self):
        return self.data["next_member_idx"]

    def getRngBuf(self):
        return self.data["rng"]["buf"]

    def getRngIndex(self):
        return self.data["rng"]["index"]

    def getLastProcessed(self):
        return self.data["last_processed"]

    def getNextReportIndex(self):
        return self.data["next_report_index"]

    def getElectionScheduleVersion(self):
        return self.data["election_schedule_version"]


# Data['current_election_state_active', {'round': 0, 'config': {'num_participants': 86, 'num_groups': 20},
# 'saved_seed': '0000000000000000000045AB464F6643EC69CBC24B91257A1868DF1684C8DC5C', 'round_end': '2022-07-09T14:02:37.000'}]
class CurrentElectionStateHandlerActive(CurrentElectionStateHandler):
    def __init__(self, data: dict):
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_ACTIVE, data, EdenBotMode.ELECTION)

    def getRound(self):
        return self.data["round"]

    def getConfigNumParticipants(self):
        return self.data["config"]["num_participants"]

    def getConfigNumGroups(self):
        return self.data["config"]["num_groups"]

    def getConfigSavedSeed(self):
        return self.data["saved_seed"]

    def getConfigRoundEnd(self):
        return self.data["round_end"]

    def customActions(self,
                      election: Election,
                      groupManagement: GroupManagement,
                      database: Database,
                      edenData: EdenData,
                      communication: Communication,
                      modeDemo: ModeDemo = None):
        assert isinstance(election, Election), "election is not an instance of Election"
        assert isinstance(groupManagement, GroupManagement), "groupManagement must be a GroupManagement object"
        assert isinstance(database, Database), "database must be a Database object"
        assert isinstance(edenData, EdenData), "edenData must be a EdenData object"
        assert isinstance(communication, Communication), "communication must be a Communication object"
        assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be a ModeDemo object or None"
        LOG.debug("Custom actions for CURRENT_ELECTION_STATE_ACTIVE")

        electionStatusIDfromDB: ElectionStatus = database.getElectionStatus(self.currentElectionState)
        if electionStatusIDfromDB == None:
            LOG.exception("'Election status' not found in database")
            raise Exception("'Election status' not found in database")

        # setting new election + creating notification records
        election = database.setElection(election=election)

        # send notification
        reminderManagement: ReminderManagement = ReminderManagement(database=database,
                                                                    edenData=edenData,
                                                                    communication=communication,
                                                                    modeDemo=modeDemo)

        reminderManagement.createRemindersTimeIsUpIfNotExists(election=election,
                                                              round=self.getRound(),
                                                              roundEnd=datetime.fromisoformat(
                                                                  self.getConfigRoundEnd()))  # already in setElection

        groupManagement.manage(round=self.getRound(),
                               numParticipants=self.getConfigNumParticipants(),
                               numGroups=self.getConfigNumGroups(),
                               isLastRound=False,
                               height=modeDemo.currentBlockHeight if modeDemo is not None else None)

        reminderManagement.sendReminderTimeIsUpIfNeeded(election=election,
                                                        modeDemo=modeDemo,
                                                        roundEnd=datetime.fromisoformat(self.getConfigRoundEnd()))


# Data['current_election_state_final', {'seed': {'current': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF', 'start_time':
#  '2022-07-09T15:02:49.000', 'end_time': '2022-07-09T17:02:49.000'}}]
class CurrentElectionStateHandlerFinal(CurrentElectionStateHandler):
    def __init__(self, data: dict):
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_ACTIVE, data, EdenBotMode.ELECTION)

    def getSeed(self):
        return self.data["seed"]

    def getSeedCurrent(self):
        return self.data["seed"]["current"]

    def getSeedStartTime(self):
        return self.data["seed"]["start_time"]

    def getSeedEndTime(self):
        return self.data["seed"]["end_time"]

    def customActions(self, groupManagement: GroupManagement, modeDemo: ModeDemo = None):
        assert isinstance(groupManagement, GroupManagement), "groupManagement must be a GroupManagement object"
        LOG.debug("Custom actions for CURRENT_ELECTION_STATE_FINAL")
        # TODO: final state does not do anything, just congrats message, no group created or anything like that
        # group management call

        groupManagement.manage(round=99,
                               numParticipants=4,
                               numGroups=1,
                               isLastRound=True,
                               height=modeDemo.currentBlockHeight if modeDemo is not None else None)
