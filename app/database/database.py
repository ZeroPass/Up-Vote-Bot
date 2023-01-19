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
import app.database.base
from database.abi import Abi
from database.tokenService import TokenService
from database.election import Election
from database.electionStatus import ElectionStatus
from database.participant import Participant
from database.extendedParticipant import ExtendedParticipant
from database.extendedRoom import ExtendedRoom
from database.room import Room
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
            self._engine = create_engine(url, pool_recycle=3600, pool_pre_ping=True, #echo_pool=True, echo=True,
                                         poolclass=NullPool)
            self._conn = self._engine.connect()
            #self._session = scoped_session(sessionmaker(bind=self._engine, expire_on_commit=False))
            LOG.debug("Database initialized")
            connection = self._engine.connect()
            #self.SessionMaker = sessionmaker(bind=connection)
            #self.session = self.SessionMaker(autoflush=True)
            #self.session = scoped_session(self.SessionMaker)
            LOG.debug("Database initialized")

            # create tables if not exists
            self.createTables(connection=connection)

        except Exception as e:
            LOG.exception("I am unable to connect to the database: " + str(e))
            raise DatabaseExceptionConnection(str(e))

    def createTables(self, connection: sqlalchemy.engine.base.Connection):
        try:
            LOG.debug("Creating tables if not exists")
            app.database.base.Base.metadata.create_all(connection, checkfirst=True)
        except Exception as e:
            LOG.exception("Problem occurred when creating tables: " + str(e))
            raise DatabaseExceptionConnection(str(e))

    def createCsesion(self, expireOnCommit: bool = True) ->scoped_session:
        try:
            connection = self._engine.connect()
            #self.SessionMaker = sessionmaker(bind=self._conn , expire_on_commit=expireOnCommit)
            sessionMaker = sessionmaker(bind=connection, expire_on_commit=expireOnCommit)
            #sessionMaker = sessionmaker(bind=self._conn, expire_on_commit=expireOnCommit)
            Csession = scoped_session(sessionMaker)
            csession = Csession()
            return csession
        except Exception as e:
            LOG.exception(message="Problem occurred when creating session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating session: " + str(e))
    def createCsesionNotScoped(self, expireOnCommit: bool = True) ->scoped_session:
        try:
            #connection = self._engine.connect()
            csessionMaker = sessionmaker(bind=self._conn, expire_on_commit=expireOnCommit)
            csession = csessionMaker(autoflush=True)
            #sessionMaker = sessionmaker(bind=connection, expire_on_commit=expireOnCommit)
            #csession = scoped_session(sessionMaker)
            return csession
        except Exception as e:
            LOG.exception(message="Problem occurred when creating session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating session: " + str(e))

    def commitCcession(self, session: scoped_session):
        try:
            session.commit()
        except Exception as e:
            #session.rollback()
            #self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when commiting session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when commiting session: " + str(e))

    def rollbackCcession(self, session: scoped_session):
        try:
            session.rollback()
        except Exception as e:
            #session.rollback()
            #self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when commiting session: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when commiting session: " + str(e))
    def removeCcession(self, session: scoped_session):
        try:
            session.close()
        except Exception as e:
            #session.rollback()
            #self.removeCcession(session=session)
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

                #this state is not from contract - is created to store rooms, that are waiting for new election
                session.add(ElectionStatus(electionStatusID=10,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS))
                session.commit()
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when filling election statuses: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when filling election statuses: " + str(e))

    def createElectionForFreeRoomsIfNotExists(self) -> bool:
        try:
            LOG.debug("Calling createElectionForFreeRoomsIfNotExists")
            LOG.info("Check if election exists in database")

            if self.getLastElection(freeRoomElection=True):
                LOG.debug("Election exists. Do nothing")
                return True

            electionStatusIDfromDB: ElectionStatus = \
                self.getElectionStatus(CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS)
            if electionStatusIDfromDB is None:
                raise DatabaseException(message="database.createElectionForFreeRooms; election status is None")

            election: Election = Election(date=datetime(2000, 1, 1), status=electionStatusIDfromDB)
            createdElection: Election = self.setElection(election=election)

            if createdElection is None:
                raise DatabaseException(message="database.createElectionForFreeRooms; election for free room not created!")
            LOG.debug("Election for free rooms created")
            return True
        except Exception as e:
            LOG.exception(message="Problem occurred when createElectionForFreeRooms is called: " + str(e))
            return False

    def writeToken(self, name: str, value: str, expireBy: datetime):
        try:
            session = self.createCsesion(expireOnCommit=False)
            tokenService: TokenService = TokenService(name=name, value=value, expireBy=expireBy)
            LOG.error("TOKEN EXPIRESWIRITING:"+ str(expireBy))
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
            return  toReturn
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
                #LOG.error(str(executionTime) +" checkIfTokenExpired. TOKEN EXPIRES:" + str(tokenService.expireBy))
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
                                                   currentElectionState: CurrentElectionState) -> CurrentElectionState:
        assert isinstance(election, Election), "election is not of type Election"
        assert isinstance(currentElectionState,
                          CurrentElectionState), "currentElectionState is not of type CurrentElectionState"
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
            #session.rollback()
            return False
            LOG.exception(message="Problem occurred when creating reminder sent record: " + str(e))
            #raise DatabaseExceptionConnection("Problem occurred when creating reminder sent record: " + str(e))

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

    def createTimeIsUpReminder(self, reminder: Reminder, csession: scoped_session):
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
                LOG.info("Reminder(time is up) for election " + str(reminder.electionID) + " saved")
                self.removeCcession(session=session)
            else:
                LOG.info("Reminder(time is up) for election " + str(reminder.electionID) + " already exists")
                self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when creating (time's up) reminder: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating (time's up) reminder: " + str(e))

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

            if self.getRemindersCount(election) == len(alert_message_time_election_is_coming):
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

    def getReminders(self, election: Election, reminderGroup: ReminderGroup = None) -> list[Reminder]:
        assert isinstance(election, Election), "election is not Election"
        assert isinstance(reminderGroup, (ReminderGroup, type(None))), "reminderGroup is not int or None"
        try:
            session = self.createCsesion()
            if reminderGroup is None:
                cs = (
                    session.query(Reminder).filter(Reminder.electionID == election.electionID).all()
                )
            else:
                cs = (
                    session.query(Reminder).filter(Reminder.electionID == election.electionID,
                                                   Reminder.reminderGroup == reminderGroup.value).all()
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

    def getRemindersCount(self, election: Election) -> int:
        assert isinstance(election, Election)
        try:
            session = self.createCsesion()
            cs = (
                session.query(Reminder.reminderID).filter(Reminder.electionID == election.electionID).count()
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

            participant = session.query(Participant).filter(or_(func.lower(Participant.telegramID) == telegramIDwithAfna.lower(),
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
            return toReturn #if not found it returns empty array - []
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
                                                           func.lower(KnownUser.userID) == telegramID.lower()).first()
            toReturn = participant
            self.removeCcession(session=session)
            return toReturn #if not found it returns None
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
                session.query(Room).filter(Room.electionID == election.electionID).all()
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

    def getRoomsPreelection(self, election: Election, predisposedBy: str) -> list[Room]:
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(predisposedBy, str), "prediposedBy must be type of int"
        try:
            session = self.createCsesion()
            rooms = session.query(Room) \
                .order_by(Room.predisposedDateTime.desc()) \
                .filter(Room.electionID == election.electionID,
                        Room.predisposedBy == predisposedBy,
                        Room.predisposedDateTime is not None).all()
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

    def getRoomWithAllUsersBeforeElection(self, election: Election) -> Room:
        assert isinstance(election, Election)
        try:
            session = self.createCsesion()
            room = session.query(Room).filter(Room.electionID == election.electionID,
                                           Room.roomIndex == -1).first()
            if room is None:
                LOG.debug("Pre-election room for election " + str(election.electionID) + " not found")
            else:
                LOG.debug("Pre-election room for election " + str(election.electionID) + " found")
            toReturn = room
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting room: " + str(e))
            return None

    def createRooms(self, listOfRooms: list[ExtendedRoom]) -> list[Room]:
        assert isinstance(listOfRooms, list), "listOfRooms is not a list"
        try:
            session = self.createCsesion(expireOnCommit=False)
            LOG.debug("Creating rooms for election; return updated list filled with id entry")
            for room in listOfRooms:
                # iterate over all rooms to detect if they already exist
                assert isinstance(room, ExtendedRoom), "room is not a ExtendedRoom"
                session.add(room)
                #session.flush()

            session.commit()
            toReturn = listOfRooms
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when creating rooms: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating rooms: " + str(e))


    def updatePreCreatedRoom(self, room: ExtendedRoom) -> ExtendedRoom:
        assert isinstance(room, ExtendedRoom), "room must be type of Extended Room"
        try:
            session = self.createCsesion(expireOnCommit=False)
            LOG.debug("Updating pre-created room; return updated room object")

            session.query(Room).filter(Room.roomID == room.roomID) \
                .update({Room.electionID: room.electionID,
                         Room.roomIndex: room.roomIndex,
                         Room.roomNameLong: room.roomNameLong,
                         Room.round: room.round,
                         Room.roomNameShort: room.roomNameShort
                         })

            session.commit()
            toReturn = room
            self.removeCcession(session=session)
            return toReturn

        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when updating pre-created room: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when updating pre-created room: " + str(e))
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
                             Room.roomNameShort: room.roomNameShort
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
                   .update({Room.roomTelegramID: room.roomTelegramID},)
            session.commit()
            self.removeCcession(session=session)
            return True
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when updating rooms(telegramID): " + str(e))
            return False

    def delegateParticipantsToTheRoom(self, extendedParticipantsList: list[ExtendedParticipant], roomPreelection: Room):
        #must be compated with preelection room - user can be in more than one election
        try:
            session = self.createCsesion(expireOnCommit=False)
            assert isinstance(extendedParticipantsList, list), "extendedParticipantsList is not a list"
            LOG.debug("Delegate participant to the room = add RoomId to the participant")
            #session.bulk_save_objects(extendedParticipantsList, return_defaults=True, update_changed_only=True)
            for participant in extendedParticipantsList:
                if isinstance(participant, type(None)):
                    LOG.warning("Participant is None. Do not add to the database")
                    continue

                assert isinstance(participant, ExtendedParticipant), "participant is not a ExtendedParticipant"
                participantFromDBAll = session.query(Participant).filter(
                                            Participant.accountName == participant.accountName).all()

                inPreelctionRoom: list[ExtendedParticipant] = \
                    [x for x in participantFromDBAll if x.roomID == roomPreelection.roomID]
                alreadyInRoom: list[ExtendedParticipant] = \
                    [x for x in participantFromDBAll if x.roomID == participant.roomID]

                # if there are participants that are not in the filters above, means that participants participated in
                # more than one election

                if len(inPreelctionRoom) > 0:
                    LOG.debug("Participant is in pre-election room. Move him to the election room; participant" +
                              str(participant.accountName))
                    session.query(Participant).filter(Participant.accountName == participant.accountName,
                                                      Participant.roomID == roomPreelection.roomID). \
                        update({Participant.roomID: participant.roomID})
                elif len(alreadyInRoom) > 0:
                    LOG.debug("Participant is already in election room. Do nothing; participant" +
                              str(participant.accountName))
                    session.query(Participant).filter(Participant.accountName == participant.accountName) \
                            .update({Participant.roomID: participant.roomID})
                else:
                    LOG.debug("Participant is in the room from previous round. Move him to current room.")
                    #TODO: Check that if there are more than one elections
                    session.query(Participant).filter(Participant.accountName == participant.accountName) \
                                              .update({Participant.roomID: participant.roomID})

            session.commit()
            self.removeCcession(session=session)
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when updating participant to the group: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when updating participant to the group: " + str(e))

    def setElection(self, election: Election) -> Election:
        try:
            session = self.createCsesion(expireOnCommit=False)
            # get election
            electionFromDB = (
                session.query(Election).filter(Election.date == election.date).first()
            )
            if electionFromDB is None:
                LOG.debug("Election for date " + str(election.date) + " not found, creating new")
                electionFromDB = election
                session.add(electionFromDB)
                session.commit()# commit and get id in the room object
                LOG.info("Election for date " + str(electionFromDB.date) + " saved")
            else:
                LOG.debug("Election for date " + str(electionFromDB.date) + " found.")

            # create reminders
            LOG.debug("Creating reminders for election at: " + str(electionFromDB.date))
            toReturn = electionFromDB
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            session.rollback()
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred in function setElection: " + str(e))
            return None

    def electionGroupsCreated(self, election: Election, round: int, numRooms: int) -> bool:
        # are groups created for election and round?
        try:
            session = self.createCsesion()

            numberOfRooms: int = session.query(Room). \
                filter(Room.electionID == election.electionID,
                       Room.round == round,
                       Room.roomIndex != -1,
                       Room.roomTelegramID != None).count()
            toReturn = True if numberOfRooms == numRooms else False
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
                       Room.roomIndex == roomIndex).count()
            toReturn = True if numberOfRooms > 1 else False
            self.removeCcession(session=session)
            return toReturn
        except Exception as e:
            self.removeCcession(session=session)
            LOG.exception(message="Problem occurred when getting information if group were created: " + str(e))
            return None

    def getLastElection(self, freeRoomElection: bool = False) -> Election:
        try:
            session = self.createCsesion()
            assert isinstance(freeRoomElection, bool), "freeRoomElection is not a bool"
            LOG.debug("Getting last election...")
            # get election status

            # get election
            if freeRoomElection:
                LOG.debug("... that stores free rooms")
                electionFromDB = (
                    session.query(Election)
                    .join(ElectionStatus, ElectionStatus.electionStatusID == Election.status)
                    .order_by(Election.date.desc())
                    .filter(ElectionStatus.status == CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS.value)
                    .first()
                )
            else:
                LOG.debug("...that is real")
                electionFromDB = (
                    session.query(Election)
                    .join(ElectionStatus, ElectionStatus.electionStatusID == Election.status)
                    .order_by(Election.date.desc())
                    .filter(ElectionStatus.status != CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS.value)
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

    def setMemberWithElectionIDAndWithRoomID(self, election: Election, room: Room,
                                             participants: list[Participant]):
        LOG.debug(message="Setting member with electionID and with roomID")
        assert isinstance(election, Election), "election is not a Election"
        assert isinstance(room, Room), "room is not a Room"
        assert isinstance(participants, list), "participants is not a list"
        try:
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
                        Room.roomTelegramID == room.roomTelegramID
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
                          " created.")
            else:
                LOG.debug("Room; ElectionID+ " + str(electionFromDB.electionID) +
                          ", RoomNameShort: " + str(roomFromDB.roomNameShort) +
                          ", RoomNameLong: " + str(roomFromDB.roomNameLong) +
                          ", Round: " + str(roomFromDB.round) +
                          ", RoomIndex: " + str(roomFromDB.roomIndex) +
                          ", RoomTelegramID: " + str(roomFromDB.roomTelegramID) +
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
                                     Participant.telegramID: participant.telegramID})
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

            roomIDs = session.query(Room.roomID).filter(Room.electionID == election.electionID).all()
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
            LOG.exception(message="Problem occurred when getting members: " + str(e))
            return None

    def getMembersInElectionRoundNotYetSend(self, election: Election, reminder: Reminder) -> list[Participant]:
        assert isinstance(election, Election), "election is not of type Election"
        assert isinstance(reminder, Reminder), "remionder is not of type Reminder"
        try:
            session = self.createCsesion()

            reminderSentParticipant = session.query(ReminderSent.accountName) \
                .filter(ReminderSent.reminderID == reminder.reminderID#,
                        #ReminderSent.sendStatus == ReminderSendStatus.SEND.value #not send again, no matter of reason
                        ).all()
            reminderSentParticipant = [i[0] for i in reminderSentParticipant]

            result = session.query(Room, Participant) \
                .join(Participant, Participant.roomID == Room.roomID) \
                .order_by(Room.roomID.desc()) \
                .filter(Room.round == reminder.round,
                        Room.roomIndex >= 0,
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

    def getUsersInRoom(self, roomTelegramID: str) -> list[Participant]:
        assert isinstance(roomTelegramID, str), "roomTelegramID must be str"
        try:
            session = self.createCsesion()

            if roomTelegramID[0] == "@":
                roomTelegramIDwithAfna = roomTelegramID
                roomTelegramID = roomTelegramID[1:]
            else:
                roomTelegramIDwithAfna = "@" + roomTelegramID
                roomTelegramID = roomTelegramID

            session = self.createCsesion()
            participant = session.query(Participant).filter(
                or_(func.lower(Participant.telegramID) == roomTelegramIDwithAfna.lower(),
                    func.lower(Participant.telegramID) == roomTelegramID.lower()
                    )).first()


            roomIDs = session.query(Room.roomID).filter(or_(Room.roomTelegramID == str(roomTelegramID),
                                                              Room.roomTelegramID == str(roomTelegramIDwithAfna)
                                                            )).all()
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
    print("Hello World!")
    database = Database()
    # kaj = database.getUsersInRoom(1)
    list: list[ExtendedParticipant] = []


    """room1 = Room(
        electionID=1,
        round=7,
        roomIndex=3,
        roomTelegramID="kvajeto",
        roomNameLong="longlong",
        roomNameShort="shortshort",
        roomID=1
    )
    room2 = ExtendedRoom.fromRoom(room1)

    par1 = Participant(accountName="abc",
                                    roomID=1,
                                    participationStatus=True,
                                    telegramID="123",
                                    nftTemplateID=1,
                                    participantName="abc")

    par2 = ExtendedParticipant.fromParticipant(participant=par1, voteFor="def", index=2)

    list.append(ExtendedParticipant(accountName="abc",
                                    roomID=1,
                                    participationStatus=True,
                                    telegramID="123",
                                    nftTemplateID=1,
                                    participantName="abc",
                                    index=1,
                                    voteFor="abc"))
    list.append(ExtendedParticipant(accountName="abcc",
                                    roomID=1,
                                    participationStatus=True,
                                    telegramID="1234",
                                    nftTemplateID=3,
                                    participantName="abcd",
                                    index=4,
                                    voteFor="abcderf"))

    list1: list[ExtendedRoom] = []
    list1.append(ExtendedRoom(
        electionID=1,
        round=7,
        roomIndex=3,
        roomTelegramID="kvajeto",
        roomNameLong="longlong",
        roomNameShort="shortshort",
        # roomID=1
    ))
    list1.append(ExtendedRoom(
        electionID=1,
        round=7,
        roomIndex=4,
        roomTelegramID="kvajeto1",
        roomNameLong="longlong1",
        roomNameShort="shortshort1",
        # roomID=1
    ))"""
    #kvaje1 = database.createRooms(listOfRooms=list1)

    # kvaje = database.delegateParticipantsToTheRoom(extendedParticipantsList=list)
    # reminder: Reminder = Reminder(reminderID=1, electionID=1, dateTimeBefore=datetime.now())
    """database.createReminderSentRecord(reminder= reminder,
                                     participant= Participant(accountName="2luminaries1",
                                                 participationStatus=True,
                                                 telegramID="rubixloop",
                                                 nftTemplateID=1507,
                                                 roomID=2,
                                                 participantName="Sebastian Beyer"),
                                      sendStatus=1)"""
    #database.createElectionForFreeRoomsIfNotExists()

    #kva = database.getKnownUsers(botName="@edenBotTestBot")
    #kva1 = database.getKnownUsers(botName="@edenBotTestBot3")
    #kva3 = database.getKnownUser(botName="@edenBotTestBot", telegramID="4523523523")
    #kva4 = database.getKnownUser(botName="@edenBotTestBot", telegramID="nejcsKerjanc3")
    #kva5 = database.setKnownUser(botName="@edenBotTestBot", telegramID="nejcSkerjanc5", isKnown=False)
    #kva5 = database.setKnownUser(botName="@edenBotTestBot", telegramID="nejcSkerjanc5", isKnown=True)
    #neki = 8

    election: Election = Election(electionID=2,
                                  status=ElectionStatus(electionStatusID=7,
                                                       status=CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V0),
                                  date=datetime.now()
                                  )

    reminder: Reminder = Reminder(reminderID=8, electionID=2, dateTimeBefore=datetime.now(), round=0)

    #kva = database.getABI(accountName="genesis.eden")
    #kva1 = database.getABI(accountName="genesis.ede2")
    #kva2 = database.getABI(accountName="genesis.eden")

    #database.fillElectionStatuses()
    #electionStatusIDfromDB: ElectionStatus = \
    #    database.getElectionStatus(CurrentElectionState.CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS)


    #kva = database.getRoomsPreelection(predisposedBy="nejc", election=Election(electionID=10,
    #                                                                           date=datetime(2022, 10, 5, 12, 58),
    #                                                                           status=electionStatusIDfromDB))

    # database.getMembers(election=election)
    roomsAndParticipants: list[list(Room, Participant)] = database.getMembersInElectionRoundNotYetSend(election=election,
                                                                                                       reminder=reminder)

    for room, participant in roomsAndParticipants:
        print("Room: " + str(room.roomID))
        #print("Participant: " + str(participant))


    # result = database.getParticipantsWithoutReminderSentRecord(reminder=reminder)




if __name__ == "__main__":
    main()
