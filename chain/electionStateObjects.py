from enum import Enum

from additionalActionsManagement import AfterEveryRoundAdditionalActions, FinalRoundAdditionalActions
from chain import EdenData
from chain.stateElectionState import ElectCurrTable
from constants import pre_created_groups_created_groups_in_one_round, \
    pre_created_groups_how_often_creating_in_min, \
    pre_created_groups_increase_factor_registration_state, pre_created_groups_increase_factor_seeding_state, \
    upload_video_deadline_after_election_started, telegram_user_bot_name, telegram_bot_name
from database.election import ElectionRound
from dateTimeManagement import DateTimeManagement
from debugMode.modeDemo import ModeDemo
from groupManagement import GroupManagement
from log import Log
from datetime import datetime, timedelta
from constants.electionState import CurrentElectionState

from database import Election, Database, ElectionStatus

from participantsManagement import ParticipantsManagement
from afterElectionReminderManagement import AfterElectionReminderManagement
from reminderManagement import ReminderManagement
from transmission import Communication

LOG = Log(className="CurrentElectionStateHandler")


class EdenBotMode(Enum):
    NOT_ELECTION = 1,
    ELECTION = 2,


class CurrentElectionStateHandler:
    def __init__(self, state: CurrentElectionState, data: dict, edenBotMode: EdenBotMode, isInLive: bool = False):
        assert isinstance(state, CurrentElectionState), "state must be type of CurrentElectionState"
        assert isinstance(data, dict), "data must be type of dict"
        assert isinstance(edenBotMode, EdenBotMode), "edenBotMode must be type of EdenBotMode"
        assert isinstance(isInLive, bool), "isInLive must be type of bool"
        self.currentElectionState: CurrentElectionState = state
        self.data: dict = data
        self.edenBotMode: EdenBotMode = edenBotMode
        self.isInLive: bool = isInLive

        LOG.info("Setting current election state: " + str(self.currentElectionState))

    def getBotMode(self) -> EdenBotMode:
        return self.edenBotMode

    def getIsInLive(self) -> bool:
        return self.isInLive

    def customActions(self):
        """Override this method to add custom actions"""
        LOG.debug("No custom actions defined")
        pass


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

    def customActions(self, election: Election, database: Database, groupManagement: GroupManagement,
                      edenData: EdenData,
                      communication: Communication,
                      electCurr: ElectCurrTable = None,
                      modeDemo: ModeDemo = None):
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(database, Database), "database must be type of Database"
        assert isinstance(groupManagement, GroupManagement), "groupManagement must be type of GroupManagement"
        assert isinstance(edenData, EdenData), "edenData must be type of EdenData"
        assert isinstance(communication, Communication), "communication must be type of Communication"
        assert isinstance(electCurr,  (ElectCurrTable, type(None))), "electCurr must be type of ElectCurrTable or None"
        assert isinstance(modeDemo, ModeDemo) or modeDemo is None, "modeDemo must be type of ModeDemo or None"
        try:
            LOG.debug("Custom actions for CURRENT_ELECTION_STATE_REGISTRATION_V1")
            LOG.info("Saving election datetime in database")

            electionStatusIDfromDB: ElectionStatus = database.getElectionStatus(self.currentElectionState)
            if electionStatusIDfromDB == None:
                LOG.exception("'Election status' not found in database")
                raise Exception("'Election status' not found in database")

            # commented for demo only
            # write participants/member in database
            participantsManagement: ParticipantsManagement = ParticipantsManagement(edenData=edenData,
                                                                                    database=database,
                                                                                    communication=communication)

            participantsManagement.getParticipantsFromChainAndMatchWithDatabase(election=election,
                                                                                height=modeDemo.currentBlockHeight
                                                                                if modeDemo is not None else None)

            # create groups before election
            groupManagement.createPredefinedGroupsIfNeeded(
                election=election,
                dateTimeManagement=DateTimeManagement(edenData=edenData),
                totalParticipants=participantsManagement.getMembersFromDBTotal(election=election),
                newRoomsInIteration=pre_created_groups_created_groups_in_one_round,
                duration=timedelta(minutes=pre_created_groups_how_often_creating_in_min),
                increaseFactor=pre_created_groups_increase_factor_registration_state,
                createChiefDelegateGroup=False)

            # send notification
            reminderManagement: ReminderManagement = ReminderManagement(election=election,
                                                                        database=database,
                                                                        edenData=edenData,
                                                                        communication=communication,
                                                                        modeDemo=modeDemo)
            # reminderManagement.createRemindersIfNotExists(election=election) already in setElection
            reminderManagement.sendReminderIfNeeded(election=election,
                                                    modeDemo=modeDemo)

            # send reminders to upload video - only after election
            afterElectionReminderManagement: AfterElectionReminderManagement = \
                AfterElectionReminderManagement(database=database,
                                                edenData=edenData,
                                                communication=communication,
                                                modeDemo=modeDemo)

            afterElectionReminderManagement.createRemindersUploadVideoIfNotExists(
                currentElection=election,
                deadlineInMinutes=upload_video_deadline_after_election_started
            )

            deadline: int = upload_video_deadline_after_election_started
            afterElectionReminderManagement.sendReminderUploadVideIfNeeded(currentElection=election,
                                                                           deadlineInMinutes=deadline,
                                                                           electCurr=electCurr,
                                                                           modeDemo=modeDemo)

        except Exception as e:
            LOG.exception("Exception thrown when called CurrentElectionStateHandlerRegistratrionV1.customActions; "
                          "Description: " + str(e))


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

    def customActions(self, election: Election, database: Database, groupManagement: GroupManagement,
                      edenData: EdenData,
                      communication: Communication,
                      modeDemo: ModeDemo = None):
        assert isinstance(election, Election), "election is not an instance of Election"
        assert isinstance(database, Database), "database is not an instance of Database"
        assert isinstance(groupManagement, GroupManagement), "groupManagement is not an instance of GroupManagement"
        assert isinstance(edenData, EdenData), "edenData is not an instance of EdenData"
        assert isinstance(communication, Communication), "communication is not an instance of Communication"
        assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be type of ModeDemo or None"
        try:
            LOG.debug("Custom actions for CURRENT_ELECTION_STATE_SEEDING_V1")
            LOG.info("Saving election datetime in database")

            # write participants/member in database
            participantsManagement: ParticipantsManagement = ParticipantsManagement(edenData=edenData,
                                                                                    database=database,
                                                                                    communication=communication)

            participantsManagement.getParticipantsFromChainAndMatchWithDatabase(election=election,
                                                                                height=modeDemo.currentBlockHeight
                                                                                if modeDemo is not None else None)

            # create groups before election
            groupManagement.createPredefinedGroupsIfNeeded(
                election=election,
                dateTimeManagement=DateTimeManagement(edenData=edenData),
                totalParticipants=participantsManagement.getMembersFromDBTotal(election=election),
                newRoomsInIteration=pre_created_groups_created_groups_in_one_round,
                duration=timedelta(minutes=pre_created_groups_how_often_creating_in_min),
                increaseFactor=pre_created_groups_increase_factor_seeding_state,
                createChiefDelegateGroup=True,
            )

            # send notification
            reminderManagement: ReminderManagement = ReminderManagement(election=election,
                                                                        database=database,
                                                                        edenData=edenData,
                                                                        communication=communication,
                                                                        modeDemo=modeDemo)
            # reminderManagement.createRemindersIfNotExists(election=election) already in setElection
            reminderManagement.sendReminderIfNeeded(election=election,
                                                    modeDemo=modeDemo)
        except Exception as e:
            LOG.exception("Exception thrown when called CurrentElectionStateHandlerSeedingV1.customActions; "
                          "Description: " + str(e))


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
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_ACTIVE, data, EdenBotMode.ELECTION, True)
        self.isRoundChanged: tuple = (False, -1)

    def setIsRoundChanged(self, isChanged: bool = True, round: int = -1):
        self.isRoundChanged = (isChanged, round)

    def getIsRoundChanged(self) -> bool:
        if len(self.isRoundChanged) != 2:
            raise Exception("self.isRoundChanged is not a tuple with 2 elements")
        if isinstance(self.isRoundChanged[0], bool) is False:
            raise Exception("self.isRoundChanged[0] is not a bool")
        if isinstance(self.isRoundChanged[1], int) is False:
            raise Exception("self.isRoundChanged[1] is not a int")
        return self.isRoundChanged

    def getPreviousRound(self):
        if len(self.isRoundChanged) != 2:
            raise Exception("self.isRoundChanged is not a tuple with 2 elements")
        if isinstance(self.isRoundChanged[0], bool) is False:
            raise Exception("self.isRoundChanged[0] is not a bool")
        if isinstance(self.isRoundChanged[1], int) is False:
            raise Exception("self.isRoundChanged[1] is not a int")
        return self.isRoundChanged[1]

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
        try:
            assert isinstance(election, Election), "election is not an instance of Election"
            assert isinstance(groupManagement, GroupManagement), "groupManagement must be a GroupManagement object"
            assert isinstance(database, Database), "database must be a Database object"
            assert isinstance(edenData, EdenData), "edenData must be a EdenData object"
            assert isinstance(communication, Communication), "communication must be a Communication object"
            assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be a ModeDemo object or None"
            LOG.debug("Custom actions for CURRENT_ELECTION_STATE_ACTIVE")

            # send notification
            reminderManagement: ReminderManagement = ReminderManagement(election=election,
                                                                        database=database,
                                                                        edenData=edenData,
                                                                        communication=communication,
                                                                        modeDemo=modeDemo)

            reminderManagement.createRemindersTimeIsUpIfNotExists(election=election,
                                                                  round=self.getRound(),
                                                                  roundEnd=datetime.fromisoformat(
                                                                      self.getConfigRoundEnd()))

            if self.getIsRoundChanged() and 0 <= self.getPreviousRound() < ElectionRound.FINAL.value:
                # round changed -> we go to a new level of elections, do action for previous levels, do nothing
                # in first round
                additionalAction: AfterEveryRoundAdditionalActions = \
                    AfterEveryRoundAdditionalActions(election=election,
                                                     database=database,
                                                     edenData=edenData,
                                                     communication=communication,
                                                     modeDemo=modeDemo)

                additionalAction.do(election=election,
                                    round=self.getPreviousRound(),
                                    telegramUserBotName=telegram_user_bot_name,
                                    telegramBotName=telegram_bot_name)

            groupManagement.manage(election=election,
                                   round=self.getRound(),
                                   numParticipants=self.getConfigNumParticipants(),
                                   numGroups=self.getConfigNumGroups(),
                                   isLastRound=False,
                                   height=modeDemo.currentBlockHeight if modeDemo is not None else None)

            reminderManagement.sendReminderTimeIsUpIfNeeded(election=election,
                                                            modeDemo=modeDemo,
                                                            roundEnd=datetime.fromisoformat(self.getConfigRoundEnd()))
        except Exception as e:
            LOG.exception("Exception thrown when called CurrentElectionStateHandlerActive.customActions; "
                          "Description: " + str(e))


# Data['current_election_state_final', {'seed': {'current': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF', 'start_time':
#  '2022-07-09T15:02:49.000', 'end_time': '2022-07-09T17:02:49.000'}}]
class CurrentElectionStateHandlerFinal(CurrentElectionStateHandler):
    def __init__(self, data: dict):
        super().__init__(CurrentElectionState.CURRENT_ELECTION_STATE_FINAL, data, EdenBotMode.ELECTION, True)
        self.isRoundChanged: tuple = (False, -1)

    def setIsRoundChanged(self, isChanged: bool = True, round: int = -1):
        self.isRoundChanged = (isChanged, round)

    def getIsRoundChanged(self) -> bool:
        if len(self.isRoundChanged) != 2:
            raise Exception("self.isRoundChanged is not a tuple with 2 elements")
        if isinstance(self.isRoundChanged[0], bool) is False:
            raise Exception("self.isRoundChanged[0] is not a bool")
        if isinstance(self.isRoundChanged[1], int) is False:
            raise Exception("self.isRoundChanged[1] is not a int")
        return self.isRoundChanged

    def getPreviousRound(self):
        if len(self.isRoundChanged) != 2:
            raise Exception("self.isRoundChanged is not a tuple with 2 elements")
        if isinstance(self.isRoundChanged[0], bool) is False:
            raise Exception("self.isRoundChanged[0] is not a bool")
        if isinstance(self.isRoundChanged[1], int) is False:
            raise Exception("self.isRoundChanged[1] is not a int")
        return self.isRoundChanged[1]

    def getSeed(self):
        return self.data["seed"]

    def getSeedCurrent(self):
        return self.data["seed"]["current"]

    def getSeedStartTime(self):
        return self.data["seed"]["start_time"]

    def getSeedEndTime(self):
        return self.data["seed"]["end_time"]

    def customActions(self, election: Election, groupManagement: GroupManagement, modeDemo: ModeDemo = None):
        try:
            assert isinstance(election, Election), "election is not an instance of Election"
            assert isinstance(groupManagement, GroupManagement), "groupManagement must be a GroupManagement object"
            assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be a ModeDemo object or None"
            LOG.debug("Custom actions for CURRENT_ELECTION_STATE_FINAL")

            groupManagement.manage(election=election,
                                   round=ElectionRound.FINAL.value,
                                   numParticipants=4,
                                   numGroups=1,
                                   isLastRound=True,
                                   height=modeDemo.currentBlockHeight if modeDemo is not None else None)


            if self.getIsRoundChanged() and 0 <= self.getPreviousRound() < ElectionRound.FINAL.value:
                # round changed -> we go to a new level of elections, do action for previous levels, do nothing
                # in first round
                additionalAction: AfterEveryRoundAdditionalActions = \
                    AfterEveryRoundAdditionalActions(election=election,
                                                     database=groupManagement.database,
                                                     edenData=groupManagement.edenData,
                                                     communication=groupManagement.communication,
                                                     modeDemo=modeDemo)

                additionalAction.do(election=election,
                                    round=self.getPreviousRound(),
                                    telegramUserBotName=telegram_user_bot_name,
                                    telegramBotName=telegram_bot_name)

                finalRoundAdditionalActions: FinalRoundAdditionalActions = \
                                    FinalRoundAdditionalActions(election=election,
                                                                edenData=groupManagement.edenData,
                                                                database=groupManagement.database,
                                                                communication=groupManagement.communication,
                                                                modeDemo=modeDemo)
                finalRoundAdditionalActions.do(telegramBotName=telegram_bot_name,
                                               telegramUserBotName=telegram_user_bot_name)

        except Exception as e:
            LOG.exception("Exception thrown when called CurrentElectionStateHandlerFinal.customActions; "
                          "Description: " + str(e))
