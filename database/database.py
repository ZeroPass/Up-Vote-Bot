import copy
import random
from enum import Enum

import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

from constants import CurrentElectionState, ReminderGroup
from constants.electionState import ElectionStatusFromKey

from log import *
from constants.parameters import database_name, database_user, database_password, database_host, database_port, \
    alert_message_time_election_is_coming
from sqlalchemy import create_engine, func, or_, nullslast
from sqlalchemy.engine.url import URL

from datetime import datetime, timedelta
# must be before import statements
import database.base
from database.abi import Abi
from database.tokenService import TokenService
from database.election import Election
from database.electionStatus import ElectionStatus
from database.participant import Participant
from database.extendedParticipant import ExtendedParticipant
from database.extendedRoom import ExtendedRoom
from database.room import Room
from database.roomAction import RoomAction
from database.knownUser import KnownUser
from database.reminder import Reminder, ReminderSent, ReminderSendStatus

LOG = Log(className="Database")


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


ABIexception = "ABIexception"


class Database(metaclass=Singleton):
    _conn: sqlalchemy.engine.base.Connection
    _localDict = {"1": Abi(accountName="1", lastUpdate=datetime.now(), contract="2")}

    __instance = None

    """@staticmethod
    def getInstance():
        #Static access method.
        if Database.__instance == None:
            Database()
        return Database.__instance
    """

    def __init__(self):
        try:
            # 2006 mysql server has gone away error
            # https://stackoverflow.com/posts/55127866/revisions

            LOG.debug("Initializing database")
            driver = 'mysql+pymysql'
            url = URL.create(driver, database_user, database_password, database_host, database_port, database_name)
            # mysql connection
            self._engine = create_engine(url, pool_recycle=3600, pool_pre_ping=True, echo_pool=True, echo=True,
                                         poolclass=NullPool)
            self._conn = self._engine.connect()
            # self._session = scoped_session(sessionmaker(bind=self._engine, expire_on_commit=False))
            LOG.debug("Database initialized")
            connection = self._engine.connect()
            # self.SessionMaker = sessionmaker(bind=connection)
            # self.session = self.SessionMaker(autoflush=True)
            # self.session = scoped_session(self.SessionMaker)
            LOG.debug("Database initialized")

            # create tables if not exists
            self.createTables(connection=connection)

        except Exception as e:
            LOG.exception("I am unable to connect to the database: " + str(e))
            raise DatabaseExceptionConnection(str(e))

    def createTables(self, connection: sqlalchemy.engine.base.Connection):
        try:
            LOG.debug("Creating tables if not exists")
            database.base.Base.metadata.create_all(connection, checkfirst=True)
        except Exception as e:
            LOG.exception("Problem occurred when creating tables: " + str(e))
            raise DatabaseExceptionConnection(str(e))

    def createCsesion(self, expireOnCommit: bool = True) -> scoped_session:
        try:
            connection = self._engine.connect()
            # self.SessionMaker = sessionmaker(bind=self._conn , expire_on_commit=expireOnCommit)
            sessionMaker = sessionmaker(bind=connection, expire_on_commit=expireOnCommit)
            # sessionMaker = sessionmaker(bind=self._conn, expire_on_commit=expireOnCommit)
            Csession = scoped_session(sessionMaker)
            csession = Csession()
            return csession
        except Exception as e:
            LOG.exception(message="Problem occurred when creating session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating session: " + str(e))

    def createCsesionNotScoped(self, expireOnCommit: bool = True) -> scoped_session:
        try:
            # connection = self._engine.connect()
            csessionMaker = sessionmaker(bind=self._conn, expire_on_commit=expireOnCommit)
            csession = csessionMaker(autoflush=True)
            # sessionMaker = sessionmaker(bind=connection, expire_on_commit=expireOnCommit)
            # csession = scoped_session(sessionMaker)
            return csession
        except Exception as e:
            LOG.exception(message="Problem occurred when creating session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating session: " + str(e))

    def commitCcession(self, session: scoped_session):
        try:
            session.commit()
        except Exception as e:
            # session.rollback()
            # self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when commiting session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when commiting session: " + str(e))

    def rollbackCcession(self, session: scoped_session):
        try:
            session.rollback()
        except Exception as e:
            # session.rollback()
            # self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when commiting session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when commiting session: " + str(e))

    def removeCcession(self, session: scoped_session):
        try:
            session.close()
        except Exception as e:
            # session.rollback()
            # self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when commiting session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when commiting session: " + str(e))

    def fillElectionStatuses(self):
        try:
            session = self.createCsesion(expireOnCommit=False)
            electionStatuses = session.query(ElectionStatus).all()
            if len(electionStatuses) == 0:
                session.add(
                    ElectionStatus(electionStatusID=0, status=CurrentElectionState.CURRENT_ELECTION_STATE_PENDING_DATE))
                session.add(ElectionStatus(electionStatusID=1,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V0))
                session.add(
                    ElectionStatus(electionStatusID=2, status=CurrentElectionState.CURRENT_ELECTION_STATE_SEEDING_V0))
                session.add(ElectionStatus(electionStatusID=3,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_INIT_VOTERS_V0))
                session.add(
                    ElectionStatus(electionStatusID=4, status=CurrentElectionState.CURRENT_ELECTION_STATE_ACTIVE))
                session.add(
                    ElectionStatus(electionStatusID=5, status=CurrentElectionState.CURRENT_ELECTION_STATE_POST_ROUND))
                session.add(
                    ElectionStatus(electionStatusID=6, status=CurrentElectionState.CURRENT_ELECTION_STATE_FINAL))
                session.add(ElectionStatus(electionStatusID=7,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V1))
                session.add(
                    ElectionStatus(electionStatusID=8, status=CurrentElectionState.CURRENT_ELECTION_STATE_SEEDING_V1))
                session.add(ElectionStatus(electionStatusID=9,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_INIT_VOTERS_V1))

                # this state is not from contract - is created to store rooms, that are waiting for new election
                session.add(ElectionStatus(electionStatusID=10,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS))
                session.commit()
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when filling election statuses: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when filling election statuses: " + str(e))

    def createElectionForFreeRoomsIfNotExists(self, contract: str, election: Election) -> Election:
        assert isinstance(contract, str), "contract is not instance of str"
        assert isinstance(election, Election), "election is not instance of Election"
        try:
            LOG.debug("Calling createElectionForFreeRoomsIfNotExists")
            LOG.info("Check if election exists in database")

            if self.getDummyElection(election=election):
                LOG.debug("Dummy election exists. Do nothing")
                return True

            electionStatusIDfromDBfreeGroups: ElectionStatus = \
                self.getElectionStatus(CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS)
            if electionStatusIDfromDBfreeGroups is None:
                raise DatabaseException(message="database.createElectionForFreeRooms; election status is None")

            # set electionID to None, because it is not set yet
            # set status as int, not object
            election.electionID = None
            electionC = Election.copy(election=election, status=electionStatusIDfromDBfreeGroups)

            createdElection: Election = self.setElection(election=electionC,
                                                         electionStatus=electionStatusIDfromDBfreeGroups)

            if createdElection is None:
                raise DatabaseException(
                    message="database.createElectionForFreeRooms; election for free room not created!")
            LOG.debug("Election for free rooms created")
            return True
        except Exception as e:
            LOG.exception(message="Problem occurred when createElectionForFreeRooms is called: " + str(e))
            return False

    def writeToken(self, name: str, value: str, expireBy: datetime):
        try:
            session = self.createCsesion(expireOnCommit=False)
            tokenService: TokenService = TokenService(name=name, value=value, expireBy=expireBy)
            LOG.error("TOKEN EXPIRES WRITING:" + str(expireBy))
            if self.getToken(name) is None:
                session.add(tokenService)
                session.flush()
                session.commit()
            else:
                session.query(TokenService) \
                    .filter(TokenService.name == name) \
                    .update({TokenService.value: value, TokenService.expireBy: expireBy})
                session.flush()
                session.commit()
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when writing token: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when writing token: " + str(e))

    def getToken(self, name: str) -> str:
        try:
            session = self.createCsesion()
            tokenService = session.query(TokenService) \
                .filter(TokenService.name == name) \
                .first()

            LOG.info(message="Token: " + str(tokenService))
            toReturn = tokenService.value if tokenService is not None else None
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting token: " + str(e))
            return None

    def checkIfTokenExists(self, name: str) -> bool:
        try:
            session = self.createCsesion()
            LOG.debug(message="Checking if token exists: " + name)

            tokenService = session.query(TokenService) \
                .filter(TokenService.name == name) \
                .first()
            toReturn = False if tokenService is None else True
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when checking if token exists: " + str(e))
            return False

    def checkIfTokenExpired(self, name: str, executionTime: datetime) -> bool:
        try:
            LOG.debug("Checking if token expired")
            session = self.createCsesion()
            tokenService = session.query(TokenService) \
                .filter(TokenService.name == name) \
                .first()

            if tokenService is None:
                self.removeCcession(session=session)
                return True
            elif tokenService.expireBy < executionTime:
                self.removeCcession(session=session)
                return True
            else:
                self.removeCcession(session=session)
                # LOG.error(str(executionTime) +" checkIfTokenExpired. TOKEN EXPIRES:" + str(tokenService.expireBy))
                return False
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when checking if token expired: " + str(e))
            return True

    def getElectionStatus(self, currentElectionState: CurrentElectionState) -> ElectionStatus:
        try:
            session = self.createCsesion()
            electionStatus = session.query(ElectionStatus) \
                .filter(ElectionStatus.status == currentElectionState.value) \
                .first()

            LOG.info(message="Election status: " + str(electionStatus))
            toReturn = electionStatus
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting election status: " + str(e))
            return None

    def updateElectionColumnElectionStateIfChanged(self,
                                                   election: Election,
                                                   currentElectionState: CurrentElectionState
                                                   ) -> CurrentElectionState:
        assert isinstance(election, Election), "election is not of type Election"
        assert isinstance(currentElectionState, CurrentElectionState), \
            "currentElectionState is not of type CurrentElectionState"
        try:
            # function return PREVIOUS election state - not current. If election state was not changed, return None
            session = self.createCsesion(expireOnCommit=False)
            election, electionStatus = session.query(Election, ElectionStatus) \
                .join(ElectionStatus, Election.status == ElectionStatus.electionStatusID) \
                .filter(Election.electionID == election.electionID) \
                .first()

            if electionStatus.status == currentElectionState.value:
                self.removeCcession(session=session)
                return None
            else:
                LOG.info("Election state changed from " + str(election.status) + " to " +
                         str(currentElectionState.value))
                # getElectionStatus
                newElectionStatus = session.query(ElectionStatus) \
                    .filter(ElectionStatus.status == currentElectionState.value) \
                    .first()

                if newElectionStatus is None or newElectionStatus.electionStatusID is None:
                    LOG.error("Election status is None ...")
                    LOG.error("..value is " + str(currentElectionState.value))
                    raise DatabaseExceptionConnection("Election status is None ...")

                session.query(Election) \
                    .filter(Election.electionID == election.electionID) \
                    .update({Election.status: newElectionStatus.electionStatusID})
                session.commit()
                toReturn = ElectionStatusFromKey(value=electionStatus.status)
                self.removeCcession(session=session)
                return toReturn
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when updating election status in election: " + str(e))
            return None

    def createOrUpdateReminderSentRecord(self, reminder: Reminder, accountName: str, sendStatus: ReminderSendStatus,
                                         cSession=None):
        assert isinstance(reminder, Reminder)
        assert isinstance(accountName, str)
        assert isinstance(sendStatus, ReminderSendStatus)
        try:
            session = cSession
            # get election
            reminderSentRecordFromDB = (
                session.query(ReminderSent).filter(ReminderSent.accountName == accountName,
                                                   ReminderSent.reminderID == reminder.reminderID).first()
            )
            if reminderSentRecordFromDB is None:
                LOG.debug("ReminderSent for ElectionID " + str(reminder.electionID) + " and dateTimeBefore" +
                          str(reminder.dateTimeBefore) + " not found, creating new")
                reminderSentRecordFromDB = ReminderSent(reminderID=reminder.reminderID,
                                                        accountName=accountName,
                                                        sendStatus=sendStatus)
                session.add(reminderSentRecordFromDB)
                session.flush()  # commit and get id in the room object
                session.commit()
                LOG.info("ReminderSend entrance for account " + accountName + " saved")
                return True
            else:
                LOG.debug("ReminderSent for ElectionID " + str(reminder.electionID) + " and dateTimeBefore" +
                          str(reminder.dateTimeBefore) + " found, updating")
                session.query(ReminderSent).filter(ReminderSent.accountName == accountName,
                                                   ReminderSent.reminderID == reminder.reminderID) \
                    .update({ReminderSent.sendStatus: sendStatus.value})
                return True
        except Exception as e:
            # session.rollback()
            return False
            LOG.exception(message="Problem occurred when creating reminder sent record: " + str(e))
            # raise DatabaseExceptionConnection("Problem occurred when creating reminder sent record: " + str(e))

    def getParticipantsWithoutReminderSentRecord(self, reminder: Reminder) -> list[tuple[str, str, bool]]:
        # returns list of tuples (accountName, telegramID, isVoter)
        assert isinstance(reminder, Reminder)
        try:
            session = self.createCsesion()
            reminderSendRecords = session.query(ReminderSent.accountName) \
                .filter(ReminderSent.reminderID == reminder.reminderID,
                        ReminderSent.sendStatus == ReminderSendStatus.SEND.value)

            participants = session.query(Participant.accountName, Participant.telegramID,
                                         Participant.participationStatus) \
                .filter(Participant.accountName.notin_(reminderSendRecords)).all()

            toReturn = participants
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(
                message="Problem occurred when getting participants without 'reminder sent record': " + str(e))
            return None

    def createReminder(self, reminder: Reminder, csession: scoped_session):
        assert isinstance(reminder, Reminder), "reminder is not of type Reminder"
        try:
            session = self.createCsesion()
            # because of database specs we need to eliminate microseconds
            reminder.dateTimeBefore.replace(microsecond=0)
            reminderSendRecords = session.query(Reminder) \
                .filter(Reminder.electionID == reminder.electionID,
                        Reminder.reminderGroup == reminder.reminderGroup,
                        Reminder.dateTimeBefore == reminder.dateTimeBefore).first()

            if reminderSendRecords is None:
                session.add(reminder)
                session.commit()
                LOG.info("Reminder for election " + str(reminder.electionID) + " saved")
                self.removeCcession(session=session)
            else:
                LOG.info("Reminder for election " + str(reminder.electionID) + " already exists")
                self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when creating reminder: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating reminder: " + str(e))

    def createRemindersIfNotExists(self, election: Election):
        try:
            session = self.createCsesion(expireOnCommit=False)
            LOG.debug("createRemindersIfNotExists for election " + str(election.electionID))
            # check variables
            for item in alert_message_time_election_is_coming:
                if len(item) != 3:
                    raise DatabaseException("alert_message_time_election_is_coming is not in correct size")
                if isinstance(item[0], int) is False:
                    LOG.exception("alert_message_time_election_is_coming tuple[0]: "
                                  "element is not int")

                    raise DatabaseException("alert_message_time_election_is_coming tuple[0]: "
                                            "element is not int")
                if isinstance(item[1], Enum) is False:
                    LOG.exception("alert_message_time_election_is_coming tuple[1]: "
                                  "element is not ReminderGroup")

                    raise DatabaseException("alert_message_time_election_is_coming tuple[1]: "
                                            "element is not ReminderGroup")
                if isinstance(item[2], str) is False:
                    LOG.exception("alert_message_time_election_is_coming tuple[2]: "
                                  "element is not str")

                    raise DatabaseException("alert_message_time_election_is_coming tuple[2]: "
                                            "element is not str")

            if self.getRemindersCount(election=election,
                                      reminderGroup1=ReminderGroup.ATTENDED,
                                      reminderGroup2=ReminderGroup.NOT_ATTENDED) == \
                    len(alert_message_time_election_is_coming):
                LOG.debug(message="Reminders for election " + str(election.electionID) + " already exists")
                self.removeCcession(session=session)
                return

            for reminder in alert_message_time_election_is_coming:
                electionTime = election.date
                reminderTime = electionTime - timedelta(minutes=reminder[0])
                reminderObj = Reminder(electionID=election.electionID,
                                       dateTimeBefore=reminderTime,
                                       reminderGroup=reminder[1])

                # because of database specs we need to eliminate microseconds
                reminderObj.dateTimeBefore.replace(microsecond=0)

                datetimeBeforeStr: str = reminderObj.dateTimeBefore.strftime('%Y-%m-%d %H:%M:%S')
                existing_reminder = (
                    session.query(Reminder).filter(Reminder.electionID == reminderObj.electionID,
                                                   Reminder.reminderGroup == reminderObj.reminderGroup,
                                                   Reminder.dateTimeBefore == datetimeBeforeStr)
                    .first()
                )
                if existing_reminder is None:
                    LOG.debug("Reminder (with execution time " + str(election.date) + ") for election "
                              + str(election.electionID) + " not found, creating new")
                    session.add(reminderObj)
                    session.commit()
                    LOG.info("Reminder for election " + str(election.electionID) + " saved")
                else:
                    LOG.debug("Reminder for election " + str(election.electionID) + " found. Do nothing")
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when creating reminders: " + str(e))

    def getReminders(self, election: Election, reminderGroup1: ReminderGroup, reminderGroup2: ReminderGroup = None) -> list[Reminder]:
        assert isinstance(election, Election), "election is not Election"
        assert isinstance(reminderGroup1, ReminderGroup), "reminderGroup is not ReminderGroup"
        assert isinstance(reminderGroup2, (ReminderGroup, type(None))), "reminderGroup is not int or None"
        try:
            session = self.createCsesion()
            if reminderGroup2 is None:
                cs = (
                    session.query(Reminder).filter(Reminder.electionID == election.electionID,
                                                   Reminder.reminderGroup == reminderGroup1.value).all()
                )
            else:
                cs = (
                    session.query(Reminder).filter(Reminder.electionID == election.electionID,
                                                   or_(Reminder.reminderGroup == reminderGroup1.value,
                                                       Reminder.reminderGroup == reminderGroup2.value)).all()
                )
            if cs is None:
                self.removeCcession(session=session)
                return None
            toReturn = cs
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting reminders: " + str(e))
            return None

    def getRemindersCount(self, election: Election, reminderGroup1: ReminderGroup,
                          reminderGroup2: ReminderGroup = None) -> int:
        assert isinstance(election, Election), "election is not Election"
        assert isinstance(reminderGroup1, ReminderGroup), "reminderGroup1 is not ReminderGroup"
        assert isinstance(reminderGroup2, (ReminderGroup, type(None))), "reminderGroup2 is not ReminderGroup or None"
        try:
            session = self.createCsesion()
            if reminderGroup2 is None:
                # only one reminder group is given
                cs = (
                    session.query(Reminder).filter(Reminder.electionID == election.electionID,
                                                   Reminder.reminderGroup == reminderGroup1.value).count()
                )
            else:
                # two reminder groups are given
                cs = (
                    session.query(Reminder).filter(Reminder.electionID == election.electionID,
                                                   or_(Reminder.reminderGroup == reminderGroup1.value,
                                                       Reminder.reminderGroup == reminderGroup2.value)).count()
                )

            if cs is None:
                self.removeCcession(session=session)
                return None
            toReturn = cs
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting reminders: " + str(e))
            return None

    def getParticipant(self, accountName: str) -> Participant:
        assert isinstance(accountName, str), "accountName is not a string"
        try:
            session = self.createCsesion()
            participant = session.query(Participant).filter(Participant.accountName == accountName).first()
            toReturn = participant
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting participant: " + str(e))
            return None

    def getParticipantByTelegramID(self, telegramID: str) -> Participant:
        assert isinstance(telegramID, str), "telegramID is not a string"
        try:
            session = self.createCsesion()
            if telegramID[0] == "@":
                telegramIDwithAfna = telegramID
                telegramID = telegramID[1:]
            else:
                telegramIDwithAfna = "@" + telegramID
                telegramID = telegramID

            participant = session.query(Participant).filter(
                or_(func.lower(Participant.telegramID) == telegramIDwithAfna.lower(),
                    func.lower(Participant.telegramID) == telegramID.lower()
                    )).first()
            toReturn = participant
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting participant by telegramid: " + str(e))
            return None

    def getKnownUsers(self, botName: str) -> list[Participant]:
        assert isinstance(botName, str), "botName is not a string"
        try:
            session = self.createCsesion()
            participants = session.query(KnownUser).filter(KnownUser.botName == botName).all()
            toReturn = participants
            self.removeCcession(session=session)
            return toReturn  # if not found it returns empty array - []
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting known users: " + str(e))
            return None

    def getKnownUser(self, botName: str, telegramID: str) -> KnownUser:
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(telegramID, str), "telegramID is not a string"
        try:
            session = self.createCsesion()
            participant: KnownUser = session.query(KnownUser).filter(KnownUser.botName == botName,
                                                                     func.lower(
                                                                         KnownUser.userID) == telegramID.lower()).first()
            toReturn = participant
            self.removeCcession(session=session)
            return toReturn  # if not found it returns None
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting known users: " + str(e))
            return None

    def setKnownUser(self, botName: str, telegramID: str, isKnown: bool) -> bool:
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(telegramID, str), "telegramID is not a string"
        assert isinstance(isKnown, bool), "isKnown is not a bool"
        try:
            session = self.createCsesion()

            knownUser: KnownUser = session.query(KnownUser).filter(KnownUser.botName == botName,
                                                                   KnownUser.userID == telegramID.lower()).first()
            if knownUser is None:
                participant = KnownUser(botName=botName, userID=telegramID.lower(), isKnown=isKnown)
                session.add(participant)
                session.commit()
                self.removeCcession(session=session)
                return True
            else:
                knownUser.isKnown = isKnown
                session.commit()
                self.removeCcession(session=session)
                return True
        except Exception as e:
            self.rollbackCcession(session=session)
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting known users: " + str(e))
            return False

    def getRooms(self, election: Election, round: int, roomIndex) -> list[Room]:
        assert isinstance(election, Election)
        try:
            session = self.createCsesion()
            cs = (
                session.query(Room).filter(Room.electionID == election.electionID,
                                           Room.isArchived == False).all()
            )
            if cs is None:
                self.removeCcession(session=session)
                return None
            toReturn = cs
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting rooms: " + str(e))
            return None

    def getRoomWaitingRoom(self, election: Election, room: Room) -> Room:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(room, Room), "room must be type of Room"

        try:
            session = self.createCsesion()
            room = session.query(Room) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == room.predisposedBy,
                        Room.roomIndex == room.roomIndex,
                        Room.round == room.round,
                        Room.predisposedBy == room.predisposedBy,
                        Room.predisposedDateTime == room.predisposedDateTime,
                        Room.isArchived == room.isArchived).first()
            if room is None:
                LOG.debug("Waiting room for election " + str(election.electionID) + " not found")
            else:
                LOG.debug("Waiting room for election " + str(election.electionID) + " found")
            toReturn = room
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting waiting room: " + str(e))
            return None

    def createWaitingRoomOrGetExisting(self, election: Election, room: Room) -> Room:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(room, Room), "room must be type of Room"

        try:
            session = self.createCsesion()

            roomFromDB = (
                session.query(Room)
                .filter(Room.electionID == election.electionID,
                        Room.roomNameShort == room.roomNameShort,
                        Room.roomNameLong == room.roomNameLong,
                        Room.round == room.round,
                        Room.roomIndex == room.roomIndex,
                        Room.roomTelegramID == room.roomTelegramID,
                        Room.predisposedBy == room.predisposedBy,
                        Room.predisposedDateTime == room.predisposedDateTime,
                        Room.isArchived == room.isArchived
                        )
                .first()
            )
            if roomFromDB is None:
                LOG.debug("Room with room name long " + str(room.roomNameLong) + " not found, creating new")
                roomFromDB = room
                session.add(roomFromDB)
                session.flush()  # commit and get id in the room object
                session.commit()
                LOG.debug("Room; ElectionID: " + str(election.electionID) +
                          ", RoomNameShort: " + str(roomFromDB.roomNameShort) +
                          ", RoomNameLong: " + str(roomFromDB.roomNameLong) +
                          ", Round: " + str(roomFromDB.round) +
                          ", RoomIndex: " + str(roomFromDB.roomIndex) +
                          ", RoomTelegramID: " + str(roomFromDB.roomTelegramID) +
                          ", PredisposedBy: " + str(roomFromDB.predisposedBy) +
                          ", PredisposedDateTime: " + str(roomFromDB.predisposedDateTime) +
                          ", isArchived: " + str(roomFromDB.isArchived) +
                          " created.")
            else:
                LOG.debug("Waiting room for election " + str(election.electionID) + " found in the DB. Return it.")

            toReturn = roomFromDB
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting waiting room: " + str(e))
            return None

    def archiveRoom(self, room: Room):
        assert isinstance(room, Room), "room must be type of Room"
        try:
            session = self.createCsesion()
            session.query(Room).filter(Room.roomID == room.roomID).update({Room.isArchived: True})
            session.commit()
            self.removeCcession(session=session)
            return True
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when deleting room: " + str(e))
            return False

    def getRoomsPreelection(self, election: Election, predisposedBy: str) -> list[Room]:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(predisposedBy, str), "prediposedBy must be type of int"
        try:
            session = self.createCsesion()
            rooms = session.query(Room) \
                .order_by(Room.predisposedDateTime.desc()) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == predisposedBy,
                        Room.predisposedDateTime != None,
                        Room.isArchived == False).all()
            if rooms is None:
                LOG.debug("Pre-election room for election " + str(election.electionID) + " not found")
            elif len(rooms) == 0:
                LOG.debug("Pre-election room for election " + str(election.electionID) + " found, but empty")
            else:
                LOG.debug("Pre-election room for election " + str(election.electionID) + " found")
            toReturn = rooms
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting room: " + str(e))
            return None

    def getLastCreatedRoom(self, election: Election, predisposedBy: str) -> list[Room]:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(predisposedBy, str), "predisposedBy must be type of int"
        try:
            session = self.createCsesion()
            room = session.query(Room) \
                .order_by(Room.predisposedDateTime.desc()) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == predisposedBy,
                        Room.predisposedDateTime != None,
                        Room.isArchived == False).first()
            if room is None:
                LOG.debug("Pre-election last created room for election " + str(election.electionID) + " not found")
            else:
                LOG.debug("Pre-election last created room for election " + str(election.electionID) + " found")
            toReturn = room
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting room: " + str(e))
            return None

    def getAllRoomsByElection(self, election: Election, predisposedBy: str) -> list[Room]:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(predisposedBy, str), "prediposedBy must be type of str"
        try:
            LOG.debug("Getting all rooms for election " + str(election.electionID))
            session = self.createCsesion()
            rooms = session.query(Room) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == predisposedBy,
                        Room.isArchived == False).all()
            if rooms is None or len(rooms) == 0:
                LOG.debug("Rooms for election " + str(election.electionID) + " not found")
            else:
                LOG.debug("Rooms for election " + str(election.electionID) + " found")

            toReturn = rooms
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting room: " + str(e))
            return None

    def getRoomsPreelectionFilteredByRound(self, election: Election, round: int, predisposedBy: str) -> list[Room]:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(predisposedBy, str), "prediposedBy must be type of int"
        assert isinstance(round, int), "round must be type of int"
        try:
            session = self.createCsesion()
            rooms = session.query(Room) \
                .order_by(Room.roomIndex.desc()) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == predisposedBy,
                        Room.round == round,
                        Room.predisposedDateTime != None,
                        Room.isArchived == False).all()
            if rooms is None:
                LOG.debug("Pre-election room (round: " + str(round) + ") for election " + str(
                    election.electionID) + " not found")
            elif len(rooms) == 0:
                LOG.debug("Pre-election room (round: " + str(round) + ") for election " + str(
                    election.electionID) + " found, but empty")
            else:
                LOG.debug(
                    "Pre-election room (round: " + str(round) + ") for election " + str(election.electionID) + " found")
            toReturn = rooms
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting room: " + str(e))
            return None

    def getRoomPreelectionFilteredByRoundAndIndex(self, election: Election, round: int, index: int, predisposedBy: str) \
            -> list[Room]:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(predisposedBy, str), "prediposedBy must be type of int"
        assert isinstance(round, int), "round must be type of int"
        assert isinstance(index, int), "index must be type of int"
        try:
            session = self.createCsesion()
            room = session.query(Room) \
                .order_by(Room.roomIndex.desc()) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == predisposedBy,
                        Room.round == round,
                        Room.roomIndex == index,
                        Room.predisposedDateTime != None,
                        Room.isArchived == False).first()
            if room is None:
                LOG.debug(
                    "Pre-election room (round: " + str(round) + ", index: " + str(index) + ") for election " + str(
                        election.electionID) + " not found")
            else:
                LOG.debug(
                    "Pre-election room (round: " + str(round) + ", index: " + str(index) + ") for election " + str(
                        election.electionID) + " found")
            toReturn = room
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred (getRoomPreelectionFilteredByRoundAndIndex) when getting room: "
                                  + str(e))
            return None

    # def getRoomWithAllUsersBeforeElection(self, election: Election) -> Room: #probably not in use anymore
    #    assert isinstance(election, Election)
    #    try:
    #        session = self.createCsesion()
    #        room = session.query(Room).filter(Room.electionID == election.electionID,
    #                                          Room.roomIndex == -50,
    #                                          Room.isArchived == False).first()  # must be -50 not other numbers
    #        if room is None:
    #            LOG.debug("Pre-election room for election " + str(election.electionID) + " not found")
    #        else:
    #            LOG.debug("Pre-election room for election " + str(election.electionID) + " found")
    #        toReturn = room
    #        self.removeCcession(session=session)
    #        return toReturn
    #    except Exception as e:
    #        self.removeCcession(session=session)
    #        LOG.exception(message="Problem occurred when getting room: " + str(e))
    #        return None

    def createRooms(self, listOfRooms: list[ExtendedRoom]) -> list[Room]:
        assert isinstance(listOfRooms, list), "listOfRooms is not a list"
        try:
            session = self.createCsesion(expireOnCommit=False)
            LOG.debug("Creating rooms for election; return updated list filled with id entry")
            for room in listOfRooms:
                # iterate over all rooms to detect if they already exist
                assert isinstance(room, ExtendedRoom), "room is not a ExtendedRoom"
                session.add(room)
                # session.flush()

            session.commit()
            toReturn = listOfRooms
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when creating rooms: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating rooms: " + str(e))

    def updatePreCreatedRooms(self, listOfRooms: list[ExtendedRoom]) -> list[Room]:
        assert isinstance(listOfRooms, list), "listOfRooms is not a list"
        try:
            session = self.createCsesion(expireOnCommit=False)
            LOG.debug("Updating pre-created rooms; return updated list")
            for room in listOfRooms:
                # iterate over all rooms to detect if they already exist
                assert isinstance(room, ExtendedRoom), "room is not a ExtendedRoom"
                session.query(Room).filter(Room.roomID == room.roomID) \
                    .update({Room.electionID: room.electionID,
                             Room.roomIndex: room.roomIndex,
                             Room.roomNameLong: room.roomNameLong,
                             Room.round: room.round,
                             Room.roomNameShort: room.roomNameShort,
                             Room.isArchived: room.isArchived
                             })

            session.commit()
            toReturn = listOfRooms
            self.removeCcession(session=session)
            return toReturn

        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when updating pre-created rooms[list]: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when updating pre-created rooms[list]: " + str(e))

    def updateRoomTelegramID(self, room: ExtendedRoom) -> bool:
        assert isinstance(room, ExtendedRoom), "room is not a ExtendedRoom"
        try:
            session = self.createCsesion(expireOnCommit=False)
            LOG.debug("Updating rooms; it returns updated list filled with id entry")
            session.query(Room).filter(Room.roomID == room.roomID) \
                .update({Room.roomTelegramID: room.roomTelegramID}, )
            session.commit()
            self.removeCcession(session=session)
            return True
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when updating rooms(telegramID): " + str(e))
            return False

    def delegateParticipantsToTheRoom(self, extendedParticipantsList: list[ExtendedParticipant], roomPreelection: Room):
        # must be compated with preelection room - user can be in more than one election
        assert isinstance(extendedParticipantsList, list), "extendedParticipantsList is not a list"
        assert isinstance(roomPreelection, Room), "roomPreelection is not a Room"
        try:
            session = self.createCsesion(expireOnCommit=False)
            assert isinstance(extendedParticipantsList, list), "extendedParticipantsList is not a list"
            LOG.debug("Delegate participant to the room = add RoomId to the participant")
            # session.bulk_save_objects(extendedParticipantsList, return_defaults=True, update_changed_only=True)
            for participant in extendedParticipantsList:
                if isinstance(participant, type(None)):
                    LOG.warning("Participant is None. Do not add to the database")
                    continue

                assert isinstance(participant, ExtendedParticipant), "participant is not a ExtendedParticipant"
                # get all rooms that participant is in -no matter if it is pre-election or election or other
                # election
                participantFromDBAll = session.query(Participant).filter(
                    Participant.accountName == participant.accountName).all()

                if participantFromDBAll is None:
                    LOG.exception(message="Participant is not in the database. Participant: "
                                          + str(participant))

                inPreelectionRoom: list[ExtendedParticipant] = \
                    [x for x in participantFromDBAll if x.roomID == roomPreelection.roomID]
                alreadyInRoom: list[ExtendedParticipant] = \
                    [x for x in participantFromDBAll if x.roomID == participant.roomID]

                # if there are participants that are not in the filters above, means that participants participated in
                # more than one election

                if len(alreadyInRoom) > 0:
                    LOG.debug("Participant is already in election room. Do nothing; participant" +
                              str(participant.accountName))
                elif len(inPreelectionRoom) > 0:
                    LOG.debug("Participant is in the DB but not in the election room."
                              " Copy him to the election room; participant" +
                              str(participant.accountName))
                    session.add(participant)
                else:
                    LOG.info("Participant is in the DB, but not for this election.")
            session.commit()
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when adding participant in the group: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when adding participant in the group: " + str(e))

    def setElection(self, election: Election, electionStatus: ElectionStatus) -> Election:
        assert isinstance(election, Election), "election is not a Election"
        assert isinstance(electionStatus, ElectionStatus), "electionStatus is not a ElectionStatus"
        try:
            session = self.createCsesion(expireOnCommit=False)
            electionFromDB = None
            if electionStatus.status == CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS.value:
                LOG.debug("Election is dummy.")
                result = session.query(Election, ElectionStatus) \
                    .join(ElectionStatus, Election.status == ElectionStatus.electionStatusID) \
                    .filter(Election.date == election.date,
                            Election.contract == election.contract,
                            ElectionStatus.status == electionStatus.status) \
                    .first()
                if result is not None:
                    electionFromDB = result.Election
            else:
                LOG.debug("Real election.")
                result = session.query(Election, ElectionStatus) \
                    .join(ElectionStatus, Election.status == ElectionStatus.electionStatusID) \
                    .filter(Election.date == election.date,
                            Election.contract == election.contract,
                            ElectionStatus.status != CurrentElectionState.CURRENT_ELECTION_STATE_INIT_VOTERS_V1.value) \
                    .first()
                if result is not None:
                    electionFromDB = result.Election

            # in the future remove this useless if statement
            if electionFromDB is None:
                LOG.debug("Election for date " + str(election.date) + " not found, creating new")
                electionFromDB = election
                session.add(electionFromDB)
                session.commit()  # commit and get id in the room object
                LOG.info("Election for date " + str(electionFromDB.date) + " saved")
            else:
                LOG.debug("Election for date " + str(electionFromDB.date) + " found.")

            toReturn = electionFromDB
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred in function setElection: " + str(e))
            return None

    def electionGroupsCreated(self, election: Election, round: int, numRooms: int, predisposedBy: str) -> bool:
        assert isinstance(election, Election), "election is not a Election"
        assert isinstance(round, int), "round is not a int"
        assert isinstance(numRooms, int), "numRooms is not a int"
        assert isinstance(predisposedBy, str), "predisposedBy is not a str"

        # are groups created for election and round?
        try:
            session = self.createCsesion()
            rooms: Room = session.query(Room, func.count(Participant.accountName).label("count")) \
                .outerjoin(Participant, Participant.roomID == Room.roomID) \
                .filter(Room.electionID == election.electionID,
                        Room.round == round,
                        Room.roomIndex >= 0,
                        Room.predisposedBy == predisposedBy,
                        Room.isArchived == False
                        ) \
                .group_by(Room.roomID).all()

            alreadyCreated = 0
            for room, count in rooms:
                LOG.debug("Room (" + str(room.roomID) + "): " + str(room.roomNameLong) + " has " + str(
                    count) + " participants")
                if count > 0:
                    alreadyCreated += 1

            toReturn = True if numRooms == alreadyCreated else False
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting information if group were created: " + str(e))
            return None

    def isGroupCreated(self, election: Election, round: int, roomIndex: int) -> bool:
        # is groups created for election and specific round + roomIndex ?
        try:
            session = self.createCsesion()
            numberOfRooms: int = session.query(Room). \
                filter(Room.electionID == election.electionID,
                       Room.round == round,
                       Room.roomIndex == roomIndex,
                       Room.isArchived == False).count()
            toReturn = True if numberOfRooms >= 1 else False
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting information if group were created: " + str(e))
            return None

    def getDummyElection(self, election: Election) -> Election:
        assert isinstance(election, Election), "election is not a Election"
        try:
            # getting dummy election where rooms from time before election are created - other data are the same
            session = self.createCsesion()

            electionFromDB = (
                session.query(Election)
                .join(ElectionStatus, ElectionStatus.electionStatusID == Election.status)
                .order_by(Election.date.desc())
                .filter(
                    Election.date == election.date,
                    Election.contract == election.contract,
                    ElectionStatus.status == CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS.value)
                .first()
            )

            self.removeCcession(session=session)
            return electionFromDB
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting dummy election: " + str(e))
            return None

    def getLastElection(self, contract: str) -> Election:
        assert isinstance(contract, str), "contract is not a str"
        try:
            session = self.createCsesion()
            LOG.debug("Getting last election (last by datetime)... for contract: " + contract)

            # get election
            electionFromDB = (
                session.query(Election)
                .join(ElectionStatus, ElectionStatus.electionStatusID == Election.status)
                .order_by(Election.date.desc())
                .filter(
                    Election.contract == contract,
                    ElectionStatus.status != CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS.value)
                .first()
            )

            if electionFromDB is None:
                raise DatabaseException("Election not found")
            else:
                LOG.debug("Election found.")
                toReturn = electionFromDB
                self.removeCcession(session=session)
                return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred in function setElection: " + str(e))
            return None

    def getMembersWhoParticipateInElectionCount(self, room: Room) -> int:
        try:
            session = self.createCsesion()
            assert isinstance(room, Room), "room is not a Room"
            LOG.debug("Getting members who participate in election under specific room...")

            # get election
            total = (
                session.query(Participant)
                .filter(Participant.roomID == room.roomID,
                        Participant.participationStatus > 0)
                .count()
            )

            LOG.debug("Participants that participate in election has been found; total: " + str(total))
            toReturn = total
            self.removeCcession(session=session)
            return toReturn

        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred in function getMembersWhoParticipateInElectionCount: " + str(e))
            return None

    def setMemberWithElectionIDAndWithRoomID(self, election: Election, room: Room,
                                             participants: list[Participant]):
        LOG.debug(message="Setting member with electionID and with roomID")
        assert isinstance(election, Election), "election is not a Election"
        assert isinstance(room, Room), "room is not a Room"
        assert isinstance(participants, list), "participants is not a list"
        try:
            if len(participants) == 0:
                LOG.debug("No participants to set")
                return
            session = self.createCsesion(expireOnCommit=False)

            # get or create election
            electionFromDB = (
                session.query(Election)
                .filter(Election.electionID == election.electionID)
            ).first()

            if electionFromDB is None:
                LOG.debug("Election " + str(election.electionID) + " not found, creating new")
                electionFromDB = election
                session.add(electionFromDB)
                session.flush()
                LOG.debug("Election; ElectionID: " + str(electionFromDB.electionID) +
                          " Election date: " + str(electionFromDB.date) +
                          " Election status: " + str(electionFromDB.status) +
                          " created.")
            else:
                LOG.debug("Election; ElectionID: " + str(electionFromDB.electionID) +
                          " Election date: " + str(electionFromDB.date) +
                          " Election status: " + str(electionFromDB.status) +
                          " found.")

            # get or create room
            roomFromDB = (
                session.query(Room)
                .filter(Room.electionID == electionFromDB.electionID,
                        Room.roomNameShort == room.roomNameShort,
                        Room.roomNameLong == room.roomNameLong,
                        Room.round == room.round,
                        Room.roomIndex == room.roomIndex,
                        Room.roomTelegramID == room.roomTelegramID,
                        Room.isArchived == room.isArchived
                        )
                .first()
            )
            if roomFromDB is None:
                LOG.debug("Room with room name long " + str(room.roomNameLong) + " not found, creating new")
                roomFromDB = room
                session.add(roomFromDB)
                session.flush()  # commit and get id in the room object
                LOG.debug("Room; ElectionID+ " + str(electionFromDB.electionID) +
                          ", RoomNameShort: " + str(roomFromDB.roomNameShort) +
                          ", RoomNameLong: " + str(roomFromDB.roomNameLong) +
                          ", Round: " + str(roomFromDB.round) +
                          ", RoomIndex: " + str(roomFromDB.roomIndex) +
                          ", RoomTelegramID: " + str(roomFromDB.roomTelegramID) +
                          ", IsArchived: " + str(roomFromDB.isArchived) +
                          " created.")
            else:
                LOG.debug("Room; ElectionID+ " + str(electionFromDB.electionID) +
                          ", RoomNameShort: " + str(roomFromDB.roomNameShort) +
                          ", RoomNameLong: " + str(roomFromDB.roomNameLong) +
                          ", Round: " + str(roomFromDB.round) +
                          ", RoomIndex: " + str(roomFromDB.roomIndex) +
                          ", RoomTelegramID: " + str(roomFromDB.roomTelegramID) +
                          ", IsArchived: " + str(roomFromDB.isArchived) +
                          " found.")

            # get or create participant

            for participant in participants:
                participantfromDB = (
                    session.query(Participant)
                    .filter(Participant.roomID == roomFromDB.roomID,
                            Participant.accountName == participant.accountName)
                    .first()
                )
                if participantfromDB is None:
                    LOG.debug("Participant for election " + str(election.electionID) + " not found, creating new")
                    participantfromDB = participant
                    participantfromDB.roomID = roomFromDB.roomID
                    session.add(participantfromDB)
                    LOG.info("Participant; account name " + str(participant.accountName) +
                             " roomID: " + str(participant.roomID) if participant.roomID is not None
                             else "< unknown>" +
                                  " participant status: " + str(
                        participant.status) if participant.participationStatus is not None
                    else "< unknown>" +
                         " telegramID: " + str(participant.telegramID) if participant.telegramID is not None
                    else "< unknown>" +
                         " nft template id: " + str(participant.nftTemplateID) if participant.nftTemplateID is not None
                    else "< unknown>" +
                         " name: " + str(participant.name) if participant.name is not None
                    else "< unknown>" +
                         " created.")
                else:
                    LOG.info("Participant; account name " + str(participant.accountName) +
                             " roomID: " + str(participant.roomID) if participant.roomID is not None
                             else "< unknown>" +
                                  " participant status: " + str(
                        participant.status) if participant.participationStatus is not None
                    else "< unknown>" +
                         " telegramID: " + str(participant.telegramID) if participant.telegramID is not None
                    else "< unknown>" +
                         " nft template id: " + str(participant.nftTemplateID) if participant.nftTemplateID is not None
                    else "< unknown>" +
                         " name: " + str(participant.name) if participant.name is not None
                    else "< unknown>" +
                         " found.")

                    if participant != participantfromDB:
                        LOG.debug("Participant data changed from " + str(
                            participantfromDB.participationStatus) + " to " + str(
                            participant.participationStatus))

                        session.query(Participant) \
                            .filter(Participant.roomID == roomFromDB.roomID,
                                    Participant.accountName == participant.accountName) \
                            .update({Participant.participationStatus: participant.participationStatus,
                                     Participant.telegramID: participant.telegramID,
                                     Participant.nftTemplateID: participant.nftTemplateID,
                                     Participant.roomID: participant.roomID,
                                     Participant.participantName: participant.participantName})
            session.commit()
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred in function setMemberWithElectionIDAndWithRoomID: " + str(e))
            raise DatabaseException("Problem occurred in function setMemberWithElectionIDAndWithRoomID: " + str(e))

    def getMembers(self, election: Election) -> list[Participant]:
        assert isinstance(election, Election), "election is not of type Election"
        try:
            session = self.createCsesion()

            result = session.query(Room, Participant) \
                .join(Participant, Participant.roomID == Room.roomID) \
                .order_by(Room.round.asc()) \
                .filter(Room.electionID == election.electionID,
                        Room.isArchived == False)\
                .group_by(Room.roomID)\
                .all()

            toReturn = result if len(result) > 0 else None
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting members: " + str(e))
            return None

    def getMembersInRoom(self, room: Room) -> list[Participant]:
        assert isinstance(room, Room), "room is not of type Room"
        try:
            session = self.createCsesion()
            LOG.debug("Getting members who participate in election under specific room...")

            # get election
            members = (
                session.query(Participant)
                .filter(Participant.roomID == room.roomID)
                .all()
            )

            LOG.debug("Participants that participate in election has been found")
            toReturn = members
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting members in specific rom: " + str(e))
            return None

    def getMembersInElectionRoundNotYetSend(self, election: Election, reminder: Reminder) -> list[Participant]:
        assert isinstance(election, Election), "election is not of type Election"
        assert isinstance(reminder, Reminder), "remionder is not of type Reminder"
        try:
            session = self.createCsesion()

            reminderSentParticipant = session.query(ReminderSent.accountName) \
                .filter(ReminderSent.reminderID == reminder.reminderID  # ,
                        # ReminderSent.sendStatus == ReminderSendStatus.SEND.value #not send again, no matter of reason
                        ).all()
            reminderSentParticipant = [i[0] for i in reminderSentParticipant]

            result = session.query(Room, Participant) \
                .join(Participant, Participant.roomID == Room.roomID) \
                .order_by(Room.roomID.desc()) \
                .filter(Room.round == reminder.round,
                        Room.roomIndex >= 0,
                        Room.isArchived == False,
                        Participant.accountName.notin_(reminderSentParticipant)
                        ).all()

            toReturn = result
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting members: " + str(e))
            return None

    def getOneReminderSentRecord(self, reminder: Reminder, participant: Participant) -> ReminderSent:
        assert isinstance(reminder, Reminder)
        assert isinstance(participant, Participant)
        try:
            session = self.createCsesion()
            cs = (
                session.query(ReminderSent).filter(ReminderSent.reminderID == reminder.id,
                                                   ReminderSent.participantID == participant.id).first()
            )
            if cs is None:
                self.removeCcession(session=session)
                return None
            toReturn = cs
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting reminder sent record: " + str(e))
            return None

    def getAllParticipantsReminderSentRecord(self, reminder: Reminder) -> list[ReminderSent]:
        assert isinstance(reminder, Reminder)
        try:
            session = self.createCsesion()
            cs = (
                session.query(ReminderSent).filter(ReminderSent.reminderID == reminder.reminderID).all()
            )
            if cs is None:
                self.removeCcession(session=session)
                return None
            toReturn = cs
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting reminder sent record: " + str(e))
            return None

    def getRoom(self, roomTelegramID: str) -> Room:
        assert isinstance(roomTelegramID, str), "roomTelegramID must be str"
        try:
            session = self.createCsesion()
            room = session.query(Room).filter(Room.roomTelegramID == roomTelegramID,
                                                        Room.isArchived == False
                                                        ).first()
            if room is None:
                self.removeCcession(session=session)
                return None
            toReturn = room
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting room: " + str(e))
            return None

    def getUsersInRoom(self, roomTelegramID: str) -> list[Participant]:
        assert isinstance(roomTelegramID, str), "roomTelegramID must be str"
        try:
            session = self.createCsesion()

            roomIDs = session.query(Room.roomID).filter(Room.roomTelegramID == roomTelegramID,
                                                        Room.isArchived == False
                                                        ).all()
            roomIDs = [i[0] for i in roomIDs]

            cs = (session.query(Participant)
                  .filter(Participant.roomID.in_(roomIDs)).all()
                  )

            if cs is None:
                self.removeCcession(session=session)
                return None
            toReturn = cs
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting users in room: " + str(e))
            return None

    def saveOrUpdateAbi(self, accountName: str, abi: str):
        try:
            session = self.createCsesion(expireOnCommit=False)
            abiObj = Abi(accountName=accountName, contract=str.encode(abi))
            existing_abi = (
                session.query(Abi).filter(Abi.accountName == abiObj.accountName).first()
            )
            LOG.debug("Saving abi for contract: " + accountName)
            if existing_abi is None:
                # saving to memory
                self._localDict[accountName] = abiObj

                LOG.debug("ABI for contract " + accountName + " not found, creating new")
                session.add(abiObj)
                session.commit()
                LOG.info("ABI for contract " + accountName + " saved")
                self.removeCcession(session=session)
            else:
                # saving to memory
                self._localDict[accountName] = abiObj

                LOG.debug("ABI for contract " + accountName + " found, updating")
                session.query(Abi).filter(Abi.accountName == accountName).update({Abi.contract: abiObj.contract})
                session.commit()
                LOG.info("ABI for contract " + accountName + " updated")
                self.removeCcession(session=session)

        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when saving/updating abi: " + str(e))

    def getABI(self, accountName: str) -> Abi:
        assert isinstance(accountName, str)
        try:
            # return if locally stored
            if accountName in self._localDict:
                return self._localDict[accountName]

            try:
                session = self.createCsesion()
                cs = (
                    session.query(Abi).filter(Abi.accountName == accountName).first()
                )

                if cs is not None:
                    # deep copy - create in class deep copy in the future
                    self._localDict[accountName] = Abi(accountName=cs.accountName,
                                                       lastUpdate=cs.lastUpdate,
                                                       contract=cs.contract)
                toReturn = cs
                self.removeCcession(session=session)
                return toReturn
            except Exception as e:
                self.removeCcession(session=session)
                LOG.exception(message="Problem when gettting abi:" + str(e))
        except Exception as e1:
            LOG.exception(message="Problem when gettting abi:" + str(e1))


class DatabaseException(Exception):
    """Base databasde class for other exceptions"""
    pass


class DatabaseExceptionConnection(DatabaseException):
    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload  # you could add more args

    def __str__(self):
        return str(self.message)


class DatabaseAbiException(DatabaseException):
    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload  # you could add more args

    def __str__(self):
        return str(self.message)


def main():
    print("Hello world from database object!")

if __name__ == "__main__":
    main()
