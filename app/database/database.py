from enum import Enum
from typing import Tuple

import psycopg2
import pymysql
import sqlalchemy
from Cython import struct
from sqlalchemy.orm import sessionmaker, declarative_base, load_only

from app.constants import CurrentElectionState
from app.log import *
from app.constants.parameters import database_name, database_user, database_password, database_host, database_port, \
    alert_message_time_election_is_coming
from sqlalchemy import Table, Column, Integer, String, MetaData, create_engine, DateTime
from sqlalchemy.engine.url import URL

from datetime import datetime
from datetime import timedelta

LOG = Log(className="Database")

# must be before import statements
import app.database.base
from app.database.abi import Abi
from app.database.election import Election
from app.database.electionStatus import ElectionStatus
from app.database.participant import Participant
from app.database.extendedParticipant import ExtendedParticipant
from app.database.room import Room
from app.database.reminder import Reminder, ReminderSent, ReminderSendStatus


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


ABIexception = "ABIexception"


class Database(metaclass=Singleton):
    _conn: sqlalchemy.engine.base.Connection
    _localDict = {"1": "2"}

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
            LOG.debug("Initializing database")
            driver = 'mysql+pymysql'
            url = URL.create(driver, database_user, database_password, database_host, database_port, database_name)
            # mysql connection
            self._engine = create_engine(url)
            connection = self._engine.connect()
            self.SessionMaker = sessionmaker(bind=connection)
            self.session = self.SessionMaker()
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

    def fillElectionStatuses(self):
        try:
            session = self.session
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
                session.commit()
        except Exception as e:
            LOG.exception(message="Problem occurred when filling election statuses: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when filling election statuses: " + str(e))

    def getElectionStatus(self, currentElectionState: CurrentElectionState) -> ElectionStatus:
        try:
            session = self.session
            electionStatus = session.query(ElectionStatus) \
                .filter(ElectionStatus.status == currentElectionState.value) \
                .first()

            LOG.info(message="Election status: " + str(electionStatus))
            return electionStatus
        except Exception as e:
            LOG.exception(message="Problem occurred when getting election status: " + str(e))
            return None

    def createOrUpdateReminderSentRecord(self, reminder: Reminder, accountName: str, sendStatus: ReminderSendStatus):
        assert isinstance(reminder, Reminder)
        assert isinstance(accountName, str)
        assert isinstance(sendStatus, Enum)
        try:
            #####################

            session = self.session
            # get election
            reminderSentRecordFromDB = (
                session.query(ReminderSent).filter(ReminderSent.accountName == accountName and
                                                   ReminderSent.reminderID == reminder.electionID).first()
            )
            if reminderSentRecordFromDB is None:
                LOG.debug("ReminderSent for ElectionID " + str(reminder.electionID) + " and dateTimeBefore" +
                          str(reminder.dateTimeBefore) + " not found, creating new")
                reminderSentRecordFromDB = ReminderSent(reminderID=reminder.reminderID,
                                                        accountName=accountName,
                                                        sendStatus=sendStatus)
                session.add(reminderSentRecordFromDB)
                session.commit()  # commit and get id in the room object
                LOG.info("ReminderSend entrance for account " + accountName + " saved")
            else:
                LOG.debug("ReminderSent for ElectionID " + str(reminder.electionID) + " and dateTimeBefore" +
                          str(reminder.dateTimeBefore) + " found, updating")
                session.query(ReminderSent).filter(ReminderSent.accountName == accountName and
                                                   ReminderSent.reminderID == reminder.electionID). \
                    update({ReminderSent.sendStatus: sendStatus.value})
                session.commit()

        except Exception as e:
            LOG.exception(message="Problem occurred when creating reminder sent record: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating reminder sent record: " + str(e))

    def getParticipantsWithoutReminderSentRecord(self, reminder: Reminder) -> list[tuple[str, str, bool]]:
        # returns list of tuples (accountName, telegramID, isVoter)
        assert isinstance(reminder, Reminder)
        try:
            session = self.session
            reminderSendRecords = session.query(ReminderSent.accountName) \
                .filter(ReminderSent.reminderID == reminder.reminderID,
                        ReminderSent.sendStatus == ReminderSendStatus.SEND.value)

            participants = session.query(Participant.accountName, Participant.telegramID,
                                         Participant.participationStatus) \
                .filter(Participant.accountName.notin_(reminderSendRecords)).all()

            return participants
        except Exception as e:
            LOG.exception(
                message="Problem occurred when getting participants without 'reminder sent record': " + str(e))
            return None

    def createRemindersIfNotExists(self, election: Election):
        try:
            session = self.session

            if self.getRemindersCount(election) == len(alert_message_time_election_is_coming):
                LOG.debug(message="Reminders for election " + str(election.electionID) + " already exists")
                return

            for reminder in alert_message_time_election_is_coming:
                electionTime = election.date
                reminderTime = electionTime - timedelta(minutes=reminder)
                reminderObj = Reminder(electionID=election.electionID, dateTimeBefore=reminderTime)
                existing_reminder = (
                    session.query(Reminder).filter(Reminder.electionID == reminderObj.electionID,
                                                   Reminder.dateTimeBefore == reminderObj.dateTimeBefore).first()
                )
                if existing_reminder is None:
                    LOG.debug("Reminder (with execution time " + str(election.date) + ") for election "
                              + str(election.electionID) + " not found, creating new")
                    session.add(reminderObj)
                    session.commit()
                    LOG.info("Reminder for election " + str(election.electionID) + " saved")
                else:
                    LOG.debug("Reminder for election " + str(election.electionID) + " found. Do nothing")

        except Exception as e:
            LOG.exception(message="Problem occurred when creating reminders: " + str(e))

    def getReminders(self, election: Election) -> list[Reminder]:
        assert isinstance(election, Election)
        try:
            session = self.session
            cs = (
                session.query(Reminder).filter(Reminder.electionID == election.electionID).all()
            )
            if cs is None:
                return None
            return cs
        except Exception as e:
            LOG.exception(message="Problem occurred when getting reminders: " + str(e))
            return None

    def getRemindersCount(self, election: Election) -> int:
        assert isinstance(election, Election)
        try:
            session = self.session
            cs = (
                session.query(Reminder.reminderID).filter(Reminder.electionID == election.electionID).count()
            )
            if cs is None:
                return None
            return cs
        except Exception as e:
            LOG.exception(message="Problem occurred when getting reminders: " + str(e))
            return None

    def getParticipant(self, accountName: str) -> Participant:
        assert isinstance(accountName, str), "accountName is not a string"
        try:
            session = self.session
            participant = session.query(Participant).filter(Participant.accountName == accountName).first()
            return participant
        except Exception as e:
            LOG.exception(message="Problem occurred when getting participant: " + str(e))
            return None

    def createRooms(self, electionID: int, listOfRooms: list[Room]) -> list[Room]:

        assert isinstance(electionID, int), "electionID is not an int"
        assert isinstance(listOfRooms, list), "listOfRooms is not a list"
        try:
            LOG.debug("Creating rooms for election " + str(electionID) + " return updated list filled with id entry")
            session = self.session
            session.bulk_save_objects(listOfRooms, return_defaults=True)
            session.commit()
            return listOfRooms

        except Exception as e:
            LOG.exception(message="Problem occurred when creating rooms: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when creating rooms: " + str(e))

    # """, extendedParticipantsList: list(ExtendedParticipant)"""
    def delegateParticipantToTheRoom(self, extendedParticipantsList: list[ExtendedParticipant]):
        try:
            assert isinstance(extendedParticipantsList, list), "extendedParticipantsList is not a list"
            LOG.debug("Delegate participant to the room = add RoomId to the participant")
            session = self.session
            session.bulk_save_objects(extendedParticipantsList, return_defaults=True)
            session.commit()
        except Exception as e:
            LOG.exception(message="Problem occurred when updating participant to the group: " + str(e))
            raise DatabaseExceptionConnection("Problem occurred when updating participant to the group: " + str(e))

    """def setMemberWithElectionIDAndWithoutRoomID(self, election: Election, participant: Participant) -> Participant:
        LOG.debug("Setting member with electionID and without roomID")
        assert isinstance(election, Election)
        assert isinstance(participant, Participant)
        try:
            session = self.session
            # get room
            room = (
                session.query(Room)
                .filter(Room.electionID == election.id, Room.round == 0)
                .first()
            )
            if room is None:
                LOG.debug("Room for election " + str(election.id) + " not found, creating new")
                room = Room(electionID=election.id, round=0, roomName="PreElectionRoom")
                session.add(room)
                session.flush() #commit and get id in the room object
                LOG.info("Room for election " + str(election.id) + " saved")
            else:
                LOG.debug("Room for election " + str(election.id) + " found.")

            # get participant
            participantfromDB = (
                session.query(Participant).filter(Participant.roomID == room.roomID,
                                                  Participant.participantID == participant.participantID)
                .first()
            )
            if participantfromDB is None:
                LOG.debug("Participant for election " + str(election.id) + " not found, creating new")
                participantfromDB = participant
                participantfromDB.roomID = room.roomID
                session.flush(participantfromDB)
                session.commit()
                LOG.info("Participant for election " + str(election.id) + " saved")
            else:
                LOG.debug("Participant for election " + str(election.id) + " found.")

            #return participant with participandID value
            return participantfromDB

        except Exception as e:
            LOG.exception(message="Problem occurred in function setMemberWithElectionIDAndWithoutRoomID: " + str(e))"""

    def setElection(self, election: Election) -> Election:
        try:
            session = self.session
            # get election
            electionFromDB = (
                session.query(Election).filter(Election.date == election.date).first()
            )
            if electionFromDB is None:
                LOG.debug("Election for date " + str(election.date) + " not found, creating new")
                electionFromDB = election
                session.add(electionFromDB)
                session.flush()  # commit and get id in the room object
                LOG.info("Election for date " + str(electionFromDB.date) + " saved")
            else:
                LOG.debug("Election for date " + str(electionFromDB.date) + " found.")

            # create reminders
            LOG.debug("Creating reminders for election at" + str(electionFromDB.date))
            self.createRemindersIfNotExists(election=electionFromDB)
            return electionFromDB

        except Exception as e:
            LOG.exception(message="Problem occurred in function setElection: " + str(e))

    """def getElection(self, datetime: datetime):
        try:
            LOG("Getting election for date " + str(datetime))
            session = self.session
            # get election
            electionFromDB = (
                session.query(Election).filter(Election.date == datetime).first()
            )
            if electionFromDB is None:
                LOG.debug("Election for date " + str(datetime) + " not found, creating new")
                electionFromDB = Election(date=datetime)
                session.add(electionFromDB)
                session.flush()  # commit and get id in the room object
                LOG.info("Election for date " + str(electionFromDB.date) + " saved")
            else:
                LOG.debug("Election for date " + str(electionFromDB.date) + " found.")

            # create reminders
            LOG.debug("Creating reminders for election at" + str(electionFromDB.date))
            self.createRemindersIfNotExists(election=electionFromDB)
            return electionFromDB

        except Exception as e:
            LOG.exception(message="Problem occurred in function setElection: " + str(e))
        """

    def getLastElection(self) -> Election:
        try:
            LOG.debug("Getting last election")
            session = self.session
            # get election
            electionFromDB = (
                session.query(Election).order_by(Election.date.desc()).first()
            )
            if electionFromDB is None:
                LOG.debug("Election not found")
                return None
            else:
                LOG.debug("Election found.")
                return electionFromDB

        except Exception as e:
            LOG.exception(message="Problem occurred in function setElection: " + str(e))

    def setMemberWithElectionIDAndWithRoomID(self, election: Election, room: Room,
                                             participant: Participant) -> Participant:
        LOG.debug(message="Setting member with electionID and with roomID")
        assert isinstance(election, Election)
        assert isinstance(room, Room)
        assert isinstance(participant, Participant)
        try:
            session = self.session

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
                session.commit()
                LOG.info("Participant; account name" + str(participant.accountName) +
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
                LOG.info("Participant; account name" + str(participant.accountName) +
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
                        .update({Participant.participationStatus: participant.participationStatus})
                    session.commit()
            # return participant with participandID value
            return participantfromDB
        except Exception as e:
            LOG.exception(message="Problem occurred in function setMemberWithElectionIDAndWithRoomID: " + str(e))
            raise DatabaseException("Problem occurred in function setMemberWithElectionIDAndWithRoomID: " + str(e))

    def getMembers(self, election: Election) -> list[Participant]:
        assert isinstance(election, Election), "election is not of type Election"
        try:
            session = self.session

            roomIDs = session.query(Room.roomID).filter(Room.electionID == election.electionID).all()
            roomIDs = [i[0] for i in roomIDs]

            cs = (session.query(Participant)
                  .filter(Participant.roomID.in_(roomIDs)).all()
                  )

            if cs is None:
                return None
            return cs
        except Exception as e:
            LOG.exception(message="Problem occurred when getting members: " + str(e))
            return None

    def getOneReminderSentRecord(self, reminder: Reminder, participant: Participant) -> ReminderSent:
        assert isinstance(reminder, Reminder)
        assert isinstance(participant, Participant)
        try:
            session = self.session
            cs = (
                session.query(ReminderSent).filter(ReminderSent.reminderID == reminder.id,
                                                   ReminderSent.participantID == participant.id).first()
            )
            if cs is None:
                return None
            return cs
        except Exception as e:
            LOG.exception(message="Problem occurred when getting reminder sent record: " + str(e))
            return None

    def getAllParticipantsReminderSentRecord(self, reminder: Reminder) -> list[ReminderSent]:
        assert isinstance(reminder, Reminder)
        try:
            session = self.session
            cs = (
                session.query(ReminderSent).filter(ReminderSent.reminderID == reminder.reminderID).all()
            )
            if cs is None:
                return None
            return cs
        except Exception as e:
            LOG.exception(message="Problem occurred when getting reminder sent record: " + str(e))
            return None

    def getUsersInRoom(self, roomTelegramID: int) -> list[Participant]:
        assert isinstance(roomTelegramID, int), "roomTelegramID must be int"
        try:
            session = self.session

            roomIDs = session.query(Room.roomID).filter(Room.roomTelegramID == roomTelegramID).all()
            roomIDs = [i[0] for i in roomIDs]

            cs = (session.query(Participant)
                  .filter(Participant.roomID.in_(roomIDs)).all()
                  )

            if cs is None:
                return None
        except Exception as e:
            LOG.exception(message="Problem occurred when getting users in room: " + str(e))
            return None

    def saveOrUpdateAbi(self, accountName: str, abi: str):
        try:
            abiObj = Abi(accountName=accountName, contract=str.encode(abi))
            session = self.session
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
            else:
                # saving to memory
                self._localDict[accountName] = abiObj

                LOG.debug("ABI for contract " + accountName + " found, updating")
                session.query(Abi).filter(Abi.accountName == accountName).update({Abi.contract: abiObj.contract})
                session.commit()
                LOG.info("ABI for contract " + accountName + " updated")
        except Exception as e:
            LOG.exception(message="Problem occurred when saving/updating abi: " + str(e))

    def getABI(self, accountName: str) -> Abi:
        assert isinstance(accountName, str)
        try:
            # return if locally stored
            if accountName in self._localDict:
                return self._localDict[accountName]

            session = self.session
            cs = (
                session.query(Abi).filter(Abi.accountName == accountName).first()
            )
            if cs is None:
                return None
            return cs
        except Exception as e:
            self.__handle_exception(e)


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
    #kaj = database.getUsersInRoom(1)
    #list: list[ExtendedParticipant] = []
    """list.append(ExtendedParticipant(accountName="abc",
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
                                   voteFor="abcderf"))"""

    # kvaje = database.delegateParticipantToTheRoom(extendedParticipantsList=list)
    # reminder: Reminder = Reminder(reminderID=1, electionID=1, dateTimeBefore=datetime.now())
    """database.createReminderSentRecord(reminder= reminder,
                                     participant= Participant(accountName="2luminaries1",
                                                 participationStatus=True,
                                                 telegramID="rubixloop",
                                                 nftTemplateID=1507,
                                                 roomID=2,
                                                 participantName="Sebastian Beyer"),
                                      sendStatus=1)"""


    election: Election = Election(electionID=1,
                                  status=ElectionStatus(electionStatusID=7,
                                           status=CurrentElectionState.CURRENT_ELECTION_STATE_REGISTRATION_V1),
                                  date=datetime.now()
                                  )

    #database.getMembers(election=election)
    database.getUsersInRoom(roomTelegramID=-1)
    # result = database.getParticipantsWithoutReminderSentRecord(reminder=reminder)

    # database.saveOrUpdateAbi("test", "test1")
    # print(database.getABI("test"))
    # print(database.getABI("test1"))
    # database1 = Database()
    # print(database == database1)

    # database.createTables()
    # database.saveAbi("test", "test")
    # r = Database.getInstance()

    # print(singleton is new_singleton)
    i = 9


if __name__ == "__main__":
    main()
