from datetime import datetime, timedelta
from operator import attrgetter

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from requests_unixsocket import Session

from additionalActionsManagement import FinalRoundAdditionalActions
from chain import EdenData
from chain.dfuse import Response, ResponseError
from database.election import ElectionRound
# from chain.electionStateObjects import CurrentElectionStateHandlerActive, CurrentElectionStateHandlerFinal
from debugMode.modeDemo import Mode, ModeDemo
from log import Log
from constants import eden_season, eden_year, eden_portal_url_action, telegram_bot_name, default_language, \
    telegram_admins_id, CurrentElectionState, start_video_preview_path, ReminderGroup, \
    time_span_for_notification_time_is_up, telegram_user_bot_name
from database import Database, Election, ExtendedParticipant, ExtendedRoom, Reminder, ReminderSent, database
from database.room import Room
from database.participant import Participant

from constants.rawActionWeb import RawActionWeb
from participantsManagement import WaitingRoom
from text.textManagement import GroupCommunicationTextManagement

from dateTimeManagement.dateTimeManagement import DateTimeManagement

from transmission import Communication, SessionType
from transmissionCustom import ADD_AT_SIGN_IF_NOT_EXISTS

import math

import gettext

_ = gettext.gettext
__ = gettext.ngettext


class GroupManagementException(Exception):
    pass


LOG = Log(className="GroupManagement")
LOGroomName = Log(className="RoomName")
LOGroomAllocation = Log(className="RoomAllocation")
LOGgroupCalculation = Log(className="GroupCalculation")


class GroupCalculation:
    """Calculate how many groups are needed for given number of participants"""

    def __init__(self, numberOfParticipants: int):
        assert isinstance(numberOfParticipants, int), "numberOfParticipants is not an integer"
        assert numberOfParticipants > 0, "numberOfParticipants is not greater than 0"
        self.numberOfParticipants = numberOfParticipants
        self.calculated: dict[dict] = None
        self.isCalculated: bool = False

    def calculate(self, increaseFactor: float = 1.0) -> list:
        """Calculate how many groups are needed for given number of participants + increase factor
        :param increaseFactor: increase factor for number of participants (e.g. 1.2 means 20% increase,
         2.0 means 100% increase))
        :return: list of rounds
        """
        assert isinstance(increaseFactor, float), "increaseFactor is not a float"
        assert increaseFactor >= 1.0, "increaseFactor is not greater than 1.0"
        LOGgroupCalculation.debug("Get dictionary of group sizes in rounds. Dictionary key is the round number, "
                                  "value is the group size and number of participants in the group."
                                  "Number of participants: " + str(self.numberOfParticipants))

        if increaseFactor != 1.0:
            self.numberOfParticipants = int(self.numberOfParticipants * increaseFactor)
            LOGgroupCalculation.debug("Increase number of participants by factor " + str(increaseFactor) + " to " +
                                      str(self.numberOfParticipants))

        calculated: dict[dict] = self.makeElectionConfig(numParticipants=self.numberOfParticipants)
        self.isCalculated = True
        self.calculated = calculated
        return calculated.keys()

    def getGroupSizes(self, numMembers, numRounds):
        """ The same code as in the contract, but in python"""
        assert isinstance(numMembers, int), "numMembers must be an int"
        assert isinstance(numRounds, int), "numRounds must be an int"
        assert numMembers > 0, "numMembers must be greater than 0"
        assert numRounds > 0, "numRounds must be greater than 0"

        basicGroupSize = int(numMembers ** (numRounds ** -1))
        if basicGroupSize == 3:
            result = [4] * numRounds
            largeRounds = int(math.log(numMembers / (result[0] ** (numRounds - 1)) / 3) / math.log(1.25))
            result[-1] = 3
            for i in range(len(result) - largeRounds - 1, len(result) - 1):
                result[i] = 5
            return result
        elif basicGroupSize >= 6:
            result = [6] * numRounds
            result[0] = 5
            divisor = 6 ** (numRounds - 1)
            result[-1] = (numMembers + divisor - 1) / divisor
            return result
        else:
            largeRounds = int(math.log(numMembers / (basicGroupSize ** numRounds)) / math.log(
                (basicGroupSize + 1.0) / basicGroupSize))
            result = [basicGroupSize + 1] * numRounds
            for i in range(numRounds - largeRounds):
                result[i] = basicGroupSize
            return result

    def countRounds(self, numberOfParticipants: int) -> int:
        """ The same code as in the contract, but in python"""
        assert isinstance(numberOfParticipants, int), "numberOfParticipants must be an int"
        result = 1
        i = 12
        while i <= numberOfParticipants:
            result += 1
            i *= 4
        return result

    def makeElectionConfig(self, numParticipants) -> dict[dict]:
        """ The same code as in the contract, but in python"""
        assert isinstance(numParticipants, int), "numParticipants must be an int"
        assert numParticipants > 0, "numParticipants must be greater than 0"
        LOGgroupCalculation.debug("Get dictionary of group sizes in rounds. Number of participants: "
                                  + str(numParticipants))

        if numParticipants == 0:
            return []

        sizes = self.getGroupSizes(numParticipants, self.countRounds(numParticipants))
        result = {}
        nextParticipants = 1
        for i in range(len(sizes) - 1, 0, -1):
            idx = i
            participants = nextParticipants * sizes[idx]
            result[idx] = {"participants": participants,
                           "groups": nextParticipants,
                           "isLastRound": True if len(sizes) - 1 == i else False
                           # first iteration is the last (Chief delegate) round
                           }
            nextParticipants = participants
        result[0] = {"participants": numParticipants, "groups": nextParticipants, "isLastRound": False}
        return result

    def roundExists(self, round: int) -> bool:
        """Check if given round exists"""
        assert isinstance(round, int), "round is not an integer"
        assert round >= 0, "round is not greater than 0"
        if self.isCalculated:
            return round in self.calculated
        else:
            raise GroupManagementException("Group calculation is not calculated yet.")

    def getNumberOfGroups(self, round: int) -> dict:
        """Get number of groups for given round"""
        assert isinstance(round, int), "round is not an integer"
        assert round >= 0, "round is not greater than 0"
        if not self.isCalculated:
            raise GroupManagementException("Group calculation is not calculated yet.")
        if round not in self.calculated:
            raise GroupManagementException("Round " + str(round) + " does not exist.")
        LOGgroupCalculation.debug("Get number of groups for round " + str(round))
        return self.calculated[round]


class RoomName:
    def __init__(self, round: int, roomIndex: int, season: int = None, isLastRound: int = False, year: int = None):
        self.round = round
        self.roomIndex = roomIndex
        self.season = season if season is not None else eden_season
        self.isLastRound = isLastRound
        self.year = year if year is not None else datetime.now().year
        LOGroomName.debug(
            f"RoomName: round={round}, group={roomIndex}, season={season}, isLastRound={isLastRound}, year={year}")

    def nameLong(self):
        # round number should be 1 higher than the actual round number
        # Eden - Round 1, Group 1, Delegates. Season 4, Year 2022.
        if self.isLastRound:
            # Eden Chief Delegates. Season 4, Year 2022.
            LOGroomName.debug(f"Eden Chief Delegates. Season {self.season}, Year {self.year}.")
            return f"Eden Chief Delegates. Season {self.season}, Year {self.year}."
        else:
            # Eden - Round 1, Group 1, Delegates. Season 4, Year 2022.
            LOGroomName.debug(
                f"Eden - Round {self.round + 1}, Group {self.roomIndex + 1:02d}, "
                f"election.  Season {self.season}, Year {self.year}.")
            return f"Eden - Round {self.round + 1}, Group {self.roomIndex + 1:02d}, " \
                   f"election.  Season {self.season}, Year {self.year}."

    def nameShort(self):
        # round number should be 1 higher than the actual round number
        if self.isLastRound:
            # Eden Chief Delegates S4, 2022
            return f"Eden Chief Delegates S{self.season}, {self.year}"
        else:
            # Eden R1G1 Delegates S4,2022
            return f"Eden R{self.round + 1}G{self.roomIndex + 1} election S{self.season},{self.year}."


class RoomAllocation:
    # class for room alllocation, translated from eden contract; native code is in src/election.cpp
    # current url: https://github.com/gofractally/Eden/blob/main/contracts/eden/src/elections.cpp

    def __init__(self, numParticipants: int, numOfRooms: int):
        assert isinstance(numParticipants, int), "numParticipants must be an int"
        assert isinstance(numOfRooms, int), "numOfRooms must be an int"
        self.numOfRooms = numOfRooms
        self.numParticipants = numParticipants

    def groupMaxSize(self) -> int:
        return (self.numParticipants + self.numOfRooms - 1) // self.numOfRooms

    def numShortGroups(self) -> int:
        return self.groupMaxSize() * self.numOfRooms - self.numParticipants

    def numLargeGroups(self) -> int:
        return self.numOfRooms - self.numShortGroups()

    def groupMinSize(self) -> int:
        return self.groupMaxSize() - 1

    def memberIndexToGroup(self, memberIndex: int) -> int:
        # function is actually the same as on the contract in election.cpp:
        # check "uint32_t election_round_config::group_to_first_member_index(uint32_t idx) const"
        assert isinstance(memberIndex, int), "memberIndex must be an int"
        assert memberIndex < self.numParticipants, "memberIndex must be smaller than number of participants"
        LOGroomAllocation.info(f"memberIndexToGroup: memberIndex={memberIndex}")

        numLarge: int = self.numLargeGroups()
        minSize: int = self.groupMinSize()

        membersInLarge: int = (minSize + 1) * numLarge
        if memberIndex < membersInLarge:
            # print(memberIndex / (minSize + 1))
            LOGroomAllocation.info(f"memberIndexToGroup: group={math.floor(memberIndex / (minSize + 1))}")
            return math.floor(memberIndex / (minSize + 1))
        else:
            LOGroomAllocation.info(
                f"memberIndexToGroup: group={math.floor((memberIndex - membersInLarge) / minSize + numLarge)}")
            return math.floor((memberIndex - membersInLarge) / minSize + numLarge)


class Group:
    def __init__(self, roomIndex: int, round: int, roomNameShort: str, roomNameLong: str,
                 members: list[ExtendedParticipant] = None):
        assert isinstance(members, (list, type(None))), "members must be a list or None"
        assert isinstance(roomIndex, int), "roomIndex must be an int"
        assert isinstance(round, int), "round must be an int"
        assert isinstance(roomNameShort, str), "roomNameShort must be a string"
        assert isinstance(roomNameLong, str), "roomNameLong must be a string"
        self.members = members if members is not None else list[ExtendedParticipant]
        self.roomNameShort = roomNameShort
        self.roomNameLong = roomNameLong
        self.roomIndex = roomIndex
        self.round = round


class RoomArray:
    def __init__(self):
        self.rooms: list[ExtendedRoom] = []

    def getRoom(self, roomIndex: int, round: int) -> ExtendedRoom:
        for room in self.rooms:
            if room.roomIndex == roomIndex and room.round == round:
                return room
        LOG.error("RoomArray.getRoom; Room not found")
        return None

    def setRooms(self, rooms: list[ExtendedRoom]):
        assert isinstance(rooms, list), "rooms must be a list"
        self.rooms = rooms

    def appendRooms(self, rooms: list[ExtendedRoom]):
        assert isinstance(rooms, list), "rooms must be a list"
        for item in rooms:
            self.rooms.append(item)

    def getRoomArray(self) -> list[ExtendedRoom]:
        return self.rooms

    def setRoom(self, room: ExtendedRoom):
        self.rooms.append(room)

    def numRooms(self) -> int:
        return len(self.rooms)


class GroupManagement:
    def __init__(self, edenData: EdenData, database: Database, communication: Communication, mode: Mode):
        assert isinstance(edenData, EdenData), "edenData must be an EdenData object"
        assert isinstance(database, Database), "database must be a Database object"
        assert isinstance(communication, Communication), "communication must be a Communication object"
        assert isinstance(mode, Mode), "mode must be a Mode object"

        self.edenData = edenData
        self.database = database
        self.communication = communication
        self.mode = mode

    def getNumberOfGroupsFromParticipantsNumber(self, numberOfParticipants: int) -> dict:
        """Calculate how many groups are needed for given number of participants
            - numberOfParticipants: number of participants
            - returns: dict with number of groups for each round
            """
        assert isinstance(numberOfParticipants, int), "numberOfParticipants must be an int"
        LOG.debug("Get number of groups from participants number; number of participants: " + str(numberOfParticipants))

        countRounds = self.countRounds(numberOfParticipants)
        groupSizes = self.getGroupSizes(numMembers=numberOfParticipants, numRounds=countRounds)
        print(groupSizes)

        # LOG.debug("Get number of groups from participants number; number of groups: " + str(numberOfGroups))
        return None

    def createPredefinedGroupsIfNeeded(self,
                                       election: Election,
                                       dateTimeManagement: DateTimeManagement,
                                       duration: timedelta,
                                       newRoomsInIteration: int,
                                       totalParticipants: int,
                                       increaseFactor: float = 1.0,
                                       createChiefDelegateGroup: bool = False):
        """Create groups that will be ready when election is in progress
            - election: election object (needed for getting number of participants)
            - numberOfParticipants: to calculate how many groups should be created
            - duration: time between creating new groups , probably the best would be every 24 hours
            - newRoomsInIteration: how many maximal groups should be created in one iteration
            - increaseFactor: how much participants (in %) should be added to calculation of number of groups
            - createAlsoChiefDelegateGroup: if True, also create group for chief delegates
            """

        try:
            assert isinstance(election, Election), "election must be an Election object"
            assert isinstance(dateTimeManagement,
                              DateTimeManagement), "dateTimeManagement must be an DateTimeManagementObject"
            assert isinstance(duration, timedelta), "duration variable must be timedelta"
            assert isinstance(newRoomsInIteration, int), "newRoomsInIteration variable must be an int"
            assert isinstance(totalParticipants, int), "totalGroups variable must be an int"
            assert isinstance(increaseFactor, float), "increaseFactor variable must be a float"
            assert isinstance(createChiefDelegateGroup, bool), "createChiefDelegateGroup variable must be a bool"

            LOG.debug("Create predefined groups; election: " + str(election) +
                      ", total participants: " + str(totalParticipants) +
                      ", duration: " + str(duration) +
                      ", new rooms in iteration: " + str(newRoomsInIteration) +
                      ", increase factor: " + str(increaseFactor) +
                      ", create chief delegate group: " + str(createChiefDelegateGroup))

            dummyElectionForFreeRooms: Election = self.database.getDummyElection(election=election)
            if dummyElectionForFreeRooms is None:
                raise GroupManagementException("No dummy election set in database")

            # get last predefined room to get the date
            lastPredefinedRoom: Room = self.database.getLastCreatedRoom(election=dummyElectionForFreeRooms,
                                                                        predisposedBy=telegram_user_bot_name)

            currentDT: datetime = dateTimeManagement.getTime()
            if lastPredefinedRoom is None or \
                    lastPredefinedRoom.predisposedDateTime + duration < currentDT:
                LOG.debug("No predefined groups OR not enough time has passed since last creation. Start creating new "
                          "groups if needed.")

                groupCalculation: GroupCalculation = GroupCalculation(numberOfParticipants=totalParticipants)
                rounds: list = groupCalculation.calculate(increaseFactor=increaseFactor)
                if groupCalculation.isCalculated is False:
                    raise GroupManagementException("Group calculation failed")

                # how many rooms left (to create) that bot can use in this iteration
                newRoomsLeft: int = newRoomsInIteration

                for round in rounds:
                    assert isinstance(round, int), "round must be an int object"
                    LOG.debug("Round: " + str(round))

                    if groupCalculation.roundExists(round=round) is False:
                        LOG.error("Round does not exist")
                        continue
                    data: dict = groupCalculation.getNumberOfGroups(round=round)
                    assert isinstance(data, dict), "data must be a dict object"
                    assert "participants" in data, "data must contain participants"
                    assert "groups" in data, "data must contain groups"
                    assert "isLastRound" in data, "data must contain isLastRound"

                    isLastRound: bool = data['isLastRound']

                    if createChiefDelegateGroup is False and isLastRound is True:
                        LOG.info("Chief delegate group should not be created in this round. Skip it.")
                        continue

                    alreadyCreatedRooms: list[Room] = self.database.getRoomsElectionFilteredByRound(
                        election=dummyElectionForFreeRooms,
                        round=round if isLastRound is False else ElectionRound.FINAL.value,
                        predisposedBy=telegram_user_bot_name)

                    # get the highest room index
                    roomIndexToCreate = max(alreadyCreatedRooms, key=attrgetter('roomIndex')).roomIndex + 1 if \
                        len(alreadyCreatedRooms) > 0 else 0

                    if len(alreadyCreatedRooms) < int(data['groups']):
                        LOG.debug("Not enough rooms created for this round. Create new rooms.")
                        numOfGroupsToCreate = int(data['groups']) - len(alreadyCreatedRooms)

                        extendedRooms: list[ExtendedRoom] = []
                        total = min(numOfGroupsToCreate, newRoomsLeft)
                        for i in range(total):
                            try:
                                # get the name of the group
                                roomName: RoomName = RoomName(round=round,
                                                              roomIndex=roomIndexToCreate,
                                                              season=eden_season,
                                                              year=eden_year,
                                                              isLastRound=isLastRound)

                                shortName: str = roomName.nameShort()
                                longName: str = roomName.nameLong()
                                # create supergroup - cannot be just a simple group because of admin rights
                                chatID = self.communication.createSuperGroup(name=shortName,
                                                                             description=longName)
                                if chatID is None:
                                    LOG.exception("ChatID is None")
                                    raise GroupManagementException("ChatID is None")

                                # updating telegramID in database
                                self.communication.addKnownUserAndUpdateLocal(botName=telegram_bot_name,
                                                                              chatID=str(chatID))
                                # add participants to the room / supergroup
                                LOG.debug("Add bot to the room")
                                self.communication.addChatMembers(chatId=chatID, participants=[telegram_bot_name])
                                LOG.debug("Promote bot in the room to admin rights")
                                self.communication.promoteMembers(sessionType=SessionType.USER,
                                                                  chatId=chatID,
                                                                  participants=[telegram_bot_name])

                                # make sure bot has admin rights
                                inviteLink: str = self.communication.getInvitationLink(sessionType=SessionType.BOT,
                                                                                       chatId=chatID)
                                if isinstance(inviteLink, str) is False:
                                    LOG.error("Invitation link is not valid. Not private (bot-user) message "
                                              "sent to the participants")

                                room: ExtendedRoom = ExtendedRoom(electionID=dummyElectionForFreeRooms.electionID,
                                                                  isPredisposed=True,
                                                                  predisposedDateTime=currentDT,
                                                                  predisposedBy=telegram_user_bot_name,
                                                                  roomIndex=roomIndexToCreate,
                                                                  roomNameShort=shortName,
                                                                  roomNameLong=longName,
                                                                  round=round if data['isLastRound'] is False
                                                                    else ElectionRound.FINAL.value,
                                                                  roomTelegramID=str(chatID),
                                                                  shareLink=inviteLink
                                                                  )
                                extendedRooms.append(room)
                                # decrease number of rooms left - important for next round
                                newRoomsLeft -= 1
                                # increase room index
                                roomIndexToCreate += 1

                            except Exception as e:
                                LOG.exception(
                                    "Exception thrown when called GroupManagement.createPredefinedGroups.forLoop"
                                    " Description: " + str(e))

                        if len(extendedRooms) > 0:
                            self.database.createRooms(listOfRooms=extendedRooms)
                            LOG.success("Rooms are successfully saved in database; Round: " + str(round))
        except Exception as e:
            LOG.exception("Exception thrown when called GroupManagement.createPredefinedGroups."
                          " Description: " + str(e))

    def getParticipantsFromChain(self, round: int, isLastRound: bool = False, height: int = None) -> list[
        ExtendedParticipant]:
        """Get participants from chain"""
        try:
            # works only when state is CurrentElectionStateActive
            LOG.info("Get participants from chain")
            response: Response = self.edenData.getParticipants(height=height)
            if isinstance(response, ResponseError):
                raise GroupManagementException("Error when called getParticipants; Description: " + response.error)
            LOG.debug("Participants from chain: " + str(response.data))
            members = []
            if response.data is not None:
                for key, value in response.data.items():

                    if value['round'] == round or isLastRound is True:
                        if key is None:
                            LOG.error("groupManagement.getParticipantsFromChain; key is none! Skip it")
                            members.append(None)
                            continue
                        participant: Participant = self.database.getParticipant(accountName=key)
                        if participant is None:
                            LOG.error("Participant not found in db (Skip it); name:" + str(key))
                            members.append(None)
                            continue
                        # conversation to the child class because of additional fields that need to stored in it
                        extendedParticipant: extendedParticipant = ExtendedParticipant.fromParticipant(
                            participant=participant,
                            index=value['index'],
                            voteFor=value['candidate'])

                        members.append(extendedParticipant)
            return members
        except Exception as e:
            LOG.exception("Exception thrown when called GroupManagement.getParticipantsFromChain. If there is a problem"
                          "wit data structure maybe the call was not made when state is CurrentElectionStateActive"
                          " Description: "
                          + str(e))

            raise GroupManagementException(
                "Exception thrown when called GroupManagement.getParticipantsFromChain; Description: " + str(e))

    def getFreePreelectionRoom(self, election: Election, round: int, index: int, predisposedBy: str):
        assert isinstance(election, Election), "election must be Election"
        assert isinstance(round, int), "round must be int"
        assert isinstance(index, int), "index must be int"
        assert isinstance(predisposedBy, str), "predisposedBy must be str"
        try:
            # real election object has also its own duplicate (where prepared rooms from time before election
            # are stored) in database
            LOG.debug(
                "Get free room for election: " + str(election) + " round: " + str(round) + " index: " + str(index))
            dummyElectionForFreeRooms: Election = self.database.getDummyElection(election=election)
            if dummyElectionForFreeRooms is None:
                raise GroupManagementException("GroupManagement.getFreePreelectionRoom; "
                                               "No dummy election found for election: " + str(election))

            room: Room = self.database.getRoomElectionFilteredByRoundAndIndex(
                election=dummyElectionForFreeRooms,
                round=round,
                index=index,
                predisposedBy=telegram_user_bot_name)
            if isinstance(room, Room) is False:
                LOG.error("getFreePreelectionRoom; No free room found under username: " + predisposedBy +
                          " and round: " + str(round) + " and index: " + str(index) +
                          " You need to create new room live.")
                return None
            return room
        except Exception as e:
            raise GroupManagementException(
                "Exception thrown when called GroupManagement.getFreePreelectionRoom; Description: " + str(e))

    def createOfflineGroupsWithParticipants(self, election: Election, round: int, numParticipants: int, numGroups: int,
                                            isLastRound: bool = False,
                                            height: int = None) -> list[ExtendedRoom]:
        assert isinstance(election, Election), "election must be an Election object"
        assert isinstance(round, int), "round must be an int"
        assert isinstance(numParticipants, int), "numParticipants must be an int"
        assert isinstance(numGroups, int), "numGroups must be an int"
        assert isinstance(isLastRound, bool), "isLastRound must be a bool"
        assert isinstance(height, (int, type(None))), "height must be an int or None"
        """Create groups"""
        try:
            LOG.info("Create groups")

            #dummyElection: Election = self.database.getDummyElection(election=election)
            #if dummyElection is None:
            #    raise GroupManagementException("GroupManagement.createOfflineGroupsWithParticipants; "
            #                                   "No dummy election found for election: " + str(election))


            #roomArrayAlreadyCreated: RoomArray = RoomArray()
            roomArrayNewGroups: RoomArray = RoomArray()
            roomArrayPrecreatedGroups: RoomArray = RoomArray()
            for index in range(numGroups):  # from 0 to numGroups -1
                if self.database.isGroupCreated(election=election,
                                                round=round,
                                                roomIndex=index):
                    LOG.debug("Room with electionID: " + str(election.electionID) + ", round:" + str(round) +
                              ", room index: " + str(index) + " already exists")
                    #room: Room = self.database.getRoomElectionFilteredByRoundAndIndexWithoutPredisposed(
                    #                                                        election=election,
                    #                                                        round=round,
                    #                                                        index=index)
                    #if isinstance(room, Room):
                    #    roomArrayAlreadyCreated.setRoom(room=ExtendedRoom.fromRoom(room=room))
                    continue

                else:
                    LOG.debug("Room with electionID: " + str(election.electionID) + ", round:" + str(round) +
                              ", room index:" + str(index) + "does not exist. Create new one in election")
                    room: Room = self.getFreePreelectionRoom(
                        election=election,
                        round=round,
                        index=index,
                        predisposedBy=telegram_user_bot_name)

                    if room is not None:
                        LOG.debug("Free (created in the past) room found. RoomID: " + str(room.roomID))
                        extendedRoom: ExtendedRoom = ExtendedRoom.fromRoom(room=room)

                        # add to the set of groups that are precreated but need to be updated in the database
                        # (electionID, etc). Updating on DB will be done later (because of optimization)
                        extendedRoom.electionID = election.electionID  # transfer to real election
                        roomArrayPrecreatedGroups.setRoom(room=extendedRoom)
                    else:
                        LOG.debug("Free (created in the past) room NOT found. Create new one")

                        # get the name of the group
                        roomName: RoomName = RoomName(round=round,
                                                      roomIndex=index,
                                                      season=eden_season,
                                                      year=eden_year,
                                                      isLastRound=isLastRound)

                        room: ExtendedRoom = ExtendedRoom(electionID=election.electionID,
                                                          round=round,
                                                          roomIndex=index,
                                                          roomNameLong=roomName.nameLong(),
                                                          roomNameShort=roomName.nameShort())

                        roomArrayNewGroups.setRoom(room)

            LOG.debug("Number of rooms that are precreated: " + str(roomArrayPrecreatedGroups.numRooms()))
            LOG.debug("Number of rooms to create: " + str(roomArrayNewGroups.numRooms()))

            LOG.info("Writing rooms (that needs to be created) in database and getting their indexes")
            roomsListWithIndexes = self.database.createRooms(listOfRooms=roomArrayNewGroups.getRoomArray())
            roomArrayBothMerged: RoomArray = RoomArray()
            roomArrayBothMerged.setRooms(roomsListWithIndexes)
            roomArrayBothMerged.appendRooms(rooms=roomArrayPrecreatedGroups.getRoomArray())
            #roomArrayBothMerged.appendRooms(rooms=roomArrayAlreadyCreated.getRoomArray())
            LOG.info("... room creation finished. Rooms are set with IDs in database.")

            # updated one by one: because of getFreePreelectionRoom function - other way it found always same room
            LOG.info("Updating rooms (that needs to be update) in database(electionID, roomIndex, names")
            self.database.updatePreCreatedRooms(listOfRooms=roomArrayPrecreatedGroups.getRoomArray())

            LOG.info("Add participants to the rooms and write it to database")
            extendedParticipantsList: list[ExtendedParticipant] = self.getParticipantsFromChain(round=round,
                                                                                                height=height,
                                                                                                isLastRound=isLastRound)

            # last round is special case
            if isLastRound is False and len(extendedParticipantsList) != numParticipants:
                LOG.exception(
                    "GroupManagement.createGroups; Number of participants from chain is not equal to number of"
                    "participants from database in regular round (not last)")
                raise GroupManagementException("GroupManagement.createGroups; Number of participants from chain is not"
                                               "equal to number of participants from database in regular round "
                                               "(not last)")

            # Allocate users to the room
            roomAllocation: RoomAllocation = RoomAllocation(numParticipants=len(extendedParticipantsList),
                                                            numOfRooms=numGroups)
            for item in extendedParticipantsList:
                if isinstance(item, type(None)):
                    LOG.warning("Extended participant list has None value; skip it")
                    continue

                if isinstance(item, ExtendedParticipant) is False:
                    LOG.error("Item is not an ExtendedParticipant")
                    raise GroupManagementException("item is not an ExtendedParticipant object")
                LOG.info("Extended participant: " + str(item))
                roomIndex = roomAllocation.memberIndexToGroup(item.index)
                # found the room with the index (name is +1 used)
                room: ExtendedRoom = roomArrayBothMerged.getRoom(roomIndex=roomIndex, round=round)
                if room is None:
                    LOG.error("Room is not found. Just skip it.")
                    continue
                # add participant to room
                room.addMember(item)

                # add room to participant - database related
                item.roomID = room.roomID

            dElection: Election = self.database.getDummyElection(election=election)
            if dElection is None:
                raise GroupManagementException("Dummy election is not set in database")

            waitingRoom: WaitingRoom = WaitingRoom(database=self.database,
                                                   dummyElection=dElection)
            waitingRoomPreelection: Room = waitingRoom.getRoomFromDB()

            if waitingRoomPreelection is None:
                raise GroupManagementException("GroupManagement.createOfflineGroupsWithParticipants."
                                               " Preelection room is not set in database")
            self.database.delegateParticipantsToTheRoom(extendedParticipantsList=extendedParticipantsList,
                                                        roomPreelection=waitingRoomPreelection)
            LOG.info("Participants are delegated to the rooms")
            return roomArrayBothMerged.getRoomArray()
        except Exception as e:
            LOG.exception("Exception thrown when called createOfflineGroupsWithParticipants; Description: " + str(e))
            raise GroupManagementException(
                "Exception thrown when called createOfflineGroupsWithParticipants; Description: " + str(e))

    def createRoom(self, extendedRoom: ExtendedRoom, isLastRound: bool = False) -> int:
        # everything that needs to be done when a room is created and right after that
        try:

            # creates room and returns roomID
            if self.communication.isInitialized is False:
                LOG.error("Communication is not initialized")
                raise GroupManagementException("Communication is not initialized")

            if extendedRoom is None:
                LOG.error("ExtendedRoom is None")
                raise GroupManagementException("ExtendedRoom is None")

            # if room is not created yet, create it, otherwise use the existing one
            if extendedRoom.roomTelegramID is None or extendedRoom.roomTelegramID == "":
                # create supergroup - cannot be just a simple group because of admin rights
                chatID = self.communication.createSuperGroup(name=extendedRoom.roomNameShort,
                                                             description=extendedRoom.roomNameLong)
                # updating telegramID in database
                self.communication.addKnownUserAndUpdateLocal(botName=telegram_bot_name, chatID=str(chatID))

                if chatID is None:
                    LOG.exception("ChatID is None")
                    raise GroupManagementException("ChatID is None")
                extendedRoom.roomTelegramID = str(chatID)
                self.database.updateRoomTelegramID(room=extendedRoom)
            else:
                chatID = int(extendedRoom.roomTelegramID)

            self.communication.addKnownUserAndUpdateLocal(botName=telegram_bot_name, chatID=chatID)
            # add participants to the room / supergroup
            LOG.debug("Add bot to the room")
            self.communication.addChatMembers(chatId=chatID, participants=[telegram_bot_name])
            LOG.debug("Promote bot in the room to admin rights")
            self.communication.promoteMembers(sessionType=SessionType.USER,
                                              chatId=chatID,
                                              participants=[telegram_bot_name])

            # self.communication.leaveChat(sessionType=SessionType.USER, chatID=chatID) # just temporary comment out

            #
            # From this point the user bot is not allowed - bot has all rights and can do everything it needs to be done
            #

            # fist one rule! - interact only with people that interact with bot before

            membersWithInteractionWithCurrentBot: list[str] = \
                [item for item in extendedRoom.getMembersTelegramIDsIfKnown()
                 if self.database.getKnownUser(botName=telegram_bot_name, telegramID=item)]

            LOG.debug("Add participants to the room - communication part related")
            if len(membersWithInteractionWithCurrentBot) > 0:
                self.communication.addChatMembers(chatId=chatID,
                                              participants=membersWithInteractionWithCurrentBot)

            # LOG.debug("Add participants to the room - database related")
            # check if needed self.database.delegateParticipantsToTheRoom(extendedParticipantsList=extendedRoom.getMembers(),

            LOG.debug("Promote participants to admin rights")
            # make sure BOT has admin rights
            self.communication.promoteMembers(sessionType=SessionType.BOT,
                                              chatId=chatID,
                                              participants=membersWithInteractionWithCurrentBot)

            # initialize text management object
            gCtextManagement: GroupCommunicationTextManagement = \
                GroupCommunicationTextManagement(language=default_language)

            # get invitation link, store it in the database, share it with the participants, send it to private
            # chat with the bot

            # make sure bot has admin rights
            if extendedRoom.shareLink is None or extendedRoom.shareLink == '':
                inviteLink: str = self.communication.getInvitationLink(sessionType=SessionType.USER, chatId=chatID)
                self.database.updateShareLinkRoom(roomID=extendedRoom.roomID,
                                                  shareLink=inviteLink)
            else:
                inviteLink = extendedRoom.shareLink

            if isinstance(inviteLink, str) is False:
                LOG.error("Invitation link is not valid. Not private (bot-user) message sent to the participants")
            else:
                LOG.debug(
                    "Invitation link is valid. Send private (bot-user) message to the participants. This invitation"
                    "link is valid until next call of this function! Make sure you handle it properly!")
                buttons = gCtextManagement.invitationLinkToTheGroupButons(inviteLink=inviteLink)

                # send private message to the participants
                members = extendedRoom.getMembersTelegramIDsIfKnown()

                for item in members:
                    item = ADD_AT_SIGN_IF_NOT_EXISTS(item)
                    self.communication.sendMessage(sessionType=SessionType.BOT,
                                                   chatId=item,
                                                   text=gCtextManagement.invitationLinkToTheGroup(
                                                       round=extendedRoom.round, isLastRound=isLastRound),
                                                   inlineReplyMarkup=InlineKeyboardMarkup(
                                                       inline_keyboard=
                                                       [
                                                           [
                                                               InlineKeyboardButton(text=buttons[0]['text'],
                                                                                    url=buttons[0]['value']),

                                                           ]
                                                       ]
                                                   ))

            LOG.info("Send welcome message to the room")
            welcomeMessage: str = ""

            welcomeMessage += gCtextManagement.welcomeMessage(inviteLink=inviteLink,
                                                              round=extendedRoom.round,
                                                              group=extendedRoom.roomIndex + 1,
                                                              isLastRound=isLastRound)
            welcomeMessage += gCtextManagement.newLine()
            welcomeMessage += gCtextManagement.newLine()

            # head text for participant list
            welcomeMessage += gCtextManagement.participantsInTheRoom()
            welcomeMessage += gCtextManagement.newLine()
            for participant in extendedRoom.members:
                welcomeMessage += gCtextManagement.participant(accountName=participant.accountName,
                                                               participantName=
                                                               participant.participantName,
                                                               telegramID=participant.telegramID)
                welcomeMessage += gCtextManagement.newLine()
                welcomeMessage += gCtextManagement.newLine()

            # not add demo text
            # if self.mode == Mode.DEMO:
            #    welcomeMessage += gCtextManagement.newLine()
            #    welcomeMessage += gCtextManagement.newLine()
            #    welcomeMessage += gCtextManagement.demoMessageInCreateGroup()

            #welcomeMessage += gCtextManagement.newLine()
            #welcomeMessage += gCtextManagement.newLine()
            #welcomeMessage += \
            #    "Now join the Zoom link provided on the [Eden members portal](https://genesis.eden.eoscommunity.org/election)."

            self.communication.sendMessage(chatId=chatID,
                                           sessionType=SessionType.BOT,
                                           text=welcomeMessage,
                                           disableWebPagePreview=True)

            LOG.info("Show print screen how to start video call")
            if isLastRound is False:
                self.communication.sendPhoto(chatId=chatID,
                                             sessionType=SessionType.BOT,
                                             photoPath=start_video_preview_path,
                                             caption=gCtextManagement.sendPhotoHowToStartVideoCallCaption()
                                             )

            LOG.info("Creating room finished")
            return chatID
        except Exception as e:
            LOG.exception("Exception thrown when called createRoom; Description: " + str(e))
            return None

    def sendInBot(self, extendedRoom: ExtendedRoom):  # not in use
        try:
            if self.communication.isInitialized() is False:
                LOG.error("Communication is not initialized")
                raise GroupManagementException("Communication is not initialized")

            if extendedRoom is None:
                LOG.error("ExtendedRoom is None")
                raise GroupManagementException("ExtendedRoom is None")

            for participant in extendedRoom.participants:
                self.communication.sendMessage(chatID=participant.telegramID,
                                               sessionType=SessionType.BOT,
                                               text=_("Eden communication group for round %d is created. "
                                                      "You can join it here: <TODO: %s>" % (extendedRoom.round, "URL")))

        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called sendInBot; Description: " + str(e))

    def groupInitialization(self, election: Election, round: int, numParticipants: int, numGroups: int,
                            isLastRound: bool = False, height: int = None) -> Room:
        """Create, rename add user to group
            Return Room object if we are in the last round, otherwise return None
        """
        try:
            assert isinstance(election, Election), "election is not an Election object"
            assert isinstance(round, int), "round is not an int object"
            assert isinstance(numParticipants, int), "numParticipants is not an int object"
            assert isinstance(numGroups, int), "numGroups is not an int object"
            assert isinstance(isLastRound, bool), "isLastRound is not a bool object"
            # should be called only when state is CurrentElectionStateHandlerActive or CurrentElectionStateHandlerFinal
            LOG.info(message="should be called only when state is CurrentElectionStateHandlerActive "
                             "or CurrentElectionStateHandlerFinal")

            LOG.info("Initialization of group")

            rooms: list[ExtendedRoom] = self.createOfflineGroupsWithParticipants(election=election,
                                                                                 round=round,
                                                                                 numParticipants=numParticipants,
                                                                                 numGroups=numGroups,
                                                                                 isLastRound=isLastRound,
                                                                                 height=height)

            for room in rooms:
                LOG.info("Room: " + str(room) +
                         ", name: " + str(room.roomNameLong) +
                         ", ID: " + str(room.roomID) +
                         ", num of participants: " + str(len(room.getMembers())) +
                         ", participants: " + str(room.getMembers())
                         )

                # initialize names of the participants
                for participant in room.getMembers():
                    participant.telegramID = ADD_AT_SIGN_IF_NOT_EXISTS(participant.telegramID)

                chatID: int = self.createRoom(extendedRoom=room, isLastRound=isLastRound)

                LOG.info("Chat with next chatID has been created: " + str(chatID) if chatID is not None
                         else "<not created>")

            if isLastRound and len(rooms) > 0 and isinstance(rooms[0], ExtendedRoom):
                # final round- we need to know when there is a last round
                return rooms[0]
            else:
                return None
        except Exception as e:
            LOG.exception("Exception thrown when called groupInitialization; Description: " + str(e))

    def manage(self, election: Election, round: int, numParticipants: int, numGroups: int, isLastRound: bool = False,
               height: int = None):
        """Staring point of the group management code"""
        # call only when CurrentElectionState is CurrentElectionStateHandlerActive or CurrentElectionStateHandlerFinal
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(round, int), "round is not an int object"
        assert isinstance(numParticipants, int), "numParticipants is not an int object"
        assert isinstance(numGroups, int), "numGroups is not an int object"
        assert isinstance(isLastRound, (bool, type(None))), "isLastRound is not a bool object or None"
        assert isinstance(height, (int, type(None))), "height is not an int object or None"
        try:
            LOG.info("Group management started")
            # check if groups are already created
            if self.database.electionGroupsCreated(election=election,
                                                   round=round,
                                                   numRooms=numGroups,
                                                   predisposedBy=telegram_user_bot_name) is False:
                LOG.info("Groups are not created yet, creating them")
                room: ExtendedRoom = self.groupInitialization(election=election,
                                                              round=round,
                                                              numParticipants=numParticipants,
                                                              numGroups=numGroups,
                                                              isLastRound=isLastRound,
                                                              height=height)
                # if room is not None or isLastRound is True:
                # last round (only last round return no None value - just Chief Delegates group created
                # LOG.debug("Last round created. Do additional stuff (cleaning unused groups, removing bot from"
                #          "used groups, etc.")
                # additionalActions: FinalRoundAdditionalActions = FinalRoundAdditionalActions(election=election,
                #                                                                             database=self.database,
                #                                                                             edenData=self.edenData,
                #                                                                             communication=
                #                                                                             self.communication,
                #                                                                             modeDemo=self.modeDemo)

                # additionalActions.do(telegramUserBotName=telegram_user_bot_name,
                #                     telegramBotName=telegram_bot_name,
                #                     excludedRoom=room)
            else:
                LOG.info("Groups are already created")

        except Exception as e:
            LOG.exception("Exception thrown when called manage function; Description: " + str(e))


def main():
    print("Main function")
    gc1 = GroupCalculation(numberOfParticipants=76)
    yes = gc1.calculate(increaseFactor=1.0)
    print (str(yes))
    kva = gc1.getNumberOfGroups(round=0)
    kva1 = gc1.getNumberOfGroups(round=1)

    kva2 = gc1.getNumberOfGroups(round=2)
    neki = 7


if __name__ == "__main__":
    main()
