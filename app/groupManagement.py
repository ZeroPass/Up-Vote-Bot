from datetime import datetime

from requests_unixsocket import Session

from app.chain import EdenData
from app.chain.dfuse import Response, ResponseError
from app.debugMode.modeDemo import Mode
from app.log import Log
from app.constants import dfuse_api_key, eden_season, eden_year
from app.database import Database, Election, ExtendedParticipant, ExtendedRoom
from app.database.room import Room
from app.database.participant import Participant

from app.transmission import Communication, SessionType

import math

import gettext

_ = gettext.gettext
__ = gettext.ngettext


class GroupManagementException(Exception):
    pass


LOG = Log(className="GroupManagement")
LOGroomName = Log(className="RoomName")
LOGroomAllocation = Log(className="RoomAllocation")


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
        # Eden - Round 1, Group 1, Delegates. Season 4, Year 2022.
        if self.isLastRound:
            # Eden Chief Delegates. Season 4, Year 2022.
            LOGroomName.debug(f"Eden Chief Delegates. Season {self.season}, Year {self.year}.")
            return f"Eden Chief Delegates. Season {self.season}, Year {self.year}."
        else:
            # Eden - Round 1, Group 1, Delegates. Season 4, Year 2022.
            LOGroomName.debug(
                f"Eden - Round {self.round}, Group{self.roomIndex:02d}, Delegates. Season {self.season}, Year {self.year}.")
            return f"Eden - Round {self.round}, Group{self.roomIndex:02d}, Delegates. Season {self.season}, Year {self.year}."

    def nameShort(self):
        if self.isLastRound:
            # Eden Chief Delegates S4, 2022
            return f"Eden Chief Delegates S{self.season}, {self.year}"
        else:
            # Eden R1G1 Delegates S4,2022
            return f"Eden - R{self.round}G{self.roomIndex:02d} Delegates. S{self.season},{self.year}."


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
                 members: list(ExtendedParticipant) = None):
        assert isinstance(members, (list, type(None))), "members must be a list or None"
        assert isinstance(roomIndex, int), "roomIndex must be an int"
        assert isinstance(round, int), "round must be an int"
        assert isinstance(roomNameShort, str), "roomNameShort must be a string"
        assert isinstance(roomNameLong, str), "roomNameLong must be a string"
        self.members = members if members is not None else list(ExtendedParticipant)
        self.roomNameShort = roomNameShort
        self.roomNameLong = roomNameLong
        self.roomIndex = roomIndex
        self.round = round

    """def isRoomNameDefined(self) -> bool:
        return True if self.roomName is not None else False"""


class RoomArray:
    def __init__(self):
        self.rooms = list(ExtendedRoom)

    def getRoom(self, roomIndex: int, round: int) -> Room:
        for room in self.rooms:
            if room.roomIndex == roomIndex and room.round == round:
                return room
        raise GroupManagementException("RoomArray.getRoom; Room not found")

    def setRooms(self, rooms: list(ExtendedRoom)):
        assert isinstance(rooms, list), "rooms must be a list"
        self.rooms = rooms

    def getRoomArray(self) -> list(ExtendedRoom):
        return self.rooms

    def setRoom(self, room: ExtendedRoom):
        self.rooms.append(room)

    def numRooms(self) -> int:
        return len(self.rooms)


def ADD_AT_SIGN_IF_NOT_EXISTS(name: str) -> str:
    assert isinstance(name, str), "name must be a string"
    if name.startswith("@"):
        return name
    else:
        return "@" + name


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

    def getParticipantsFromChain(self, round: int, height: int = None) -> list(ExtendedParticipant):
        """Get participants from chain"""
        try:
            # works only when state is CurrentElectionStateActive
            LOG.info("Get participants from chain")
            response: Response = self.edenData.getParticipants(height=height)
            if isinstance(response, ResponseError):
                raise GroupManagementException("Error when called getParticipants; Description: " + response.error)
            LOG.debug("Participants from chain: " + str(response.data))
            members = []
            for item in response.data:
                if item['round'] == round:
                    participant: Participant = self.database.getParticipant(item['member'])
                    extendedParticipant: Participant = ExtendedParticipant(participant=participant,
                                                                           index=item['index'],
                                                                           voteFor=item['candidate'])

                    members.append(extendedParticipant)
            members.sort()
            return members
        except Exception as e:
            LOG.exception("Exception thrown when called GroupManagement.getParticipants. If there is a problem with"
                          "datat strucutre maybe the call was not made when state is CurrentElectionStateActive"
                          " Description: "
                          + str(e))
            raise GroupManagementException(
                "Exception thrown when called GroupManagement.getParticipants; Description: " + str(e))

    def getGroups(self, round: int, numParticipants: int, numGroups: int, isLastRound: bool = False,
                  height: int = None) -> list[ExtendedRoom]:
        """Create groups"""
        try:
            LOG.info("Create groups")
            # get last election
            election: Election = self.database.getLastElection()
            if election is None:
                LOG.exception("GroupManagement.createGroups; No election found!")
                raise GroupManagementException("GroupManagement.createGroups; No election found!")

            roomArray: RoomArray = RoomArray()
            for index in range(1, numGroups + 1):
                roomName: RoomName = RoomName(round=round,
                                              roomIndex=index,
                                              season=eden_season,
                                              year=eden_year,
                                              isLastRound=isLastRound)

                room: ExtendedRoom = ExtendedRoom(electionID=election.id,
                                                  round=round,
                                                  roomIndex=index,
                                                  roomNameLong=roomName.nameLong(),
                                                  roomNameShort=roomName.nameShort())

                roomArray.setRoom(room)

            LOG.debug("Number of created rooms: " + str(roomArray.numRooms()))

            LOG.info("Writing rooms to database and setting new variable with indexes in group")
            roomsListWithIndexes = self.database.createRooms(electionID=election.electionID,
                                                             listOfRooms=roomArray.getRoomArray())
            roomsArrayWithIndexes: RoomArray = RoomArray()
            roomsArrayWithIndexes.setRooms(roomsListWithIndexes)
            LOG.info("Room creation finished. Rooms are set with IDs in database")

            LOG.info("Add participants to the rooms and write it to database")
            extendedParticipantsList: list(ExtendedParticipant) = self.getParticipantsFromChain(round=round,
                                                                                                height=height)

            if len(extendedParticipantsList) != numParticipants:
                LOG.exception(
                    "GroupManagement.createGroups; Number of participants from chain is not equal to number of"
                    "participants from database")
                raise GroupManagementException("GroupManagement.createGroups; Number of participants from chain is not"
                                               "equal to number of participants from database")

            # Allocate users to the room
            roomAllocation: RoomAllocation = RoomAllocation(numParticipants=len(extendedParticipantsList),
                                                            numOfRooms=numGroups)
            for item in extendedParticipantsList:
                if isinstance(item, ExtendedParticipant) is False:
                    LOG.error("Item is not an ExtendedParticipant")
                    raise GroupManagementException("item is not an ExtendedParticipant object")
                LOG.info("Extended participant: " + str(item))
                roomIndex = roomAllocation.memberIndexToGroup(item.index)
                # found the room with the index (name is +1 used)
                room: Room = roomsArrayWithIndexes.getRoom(roomIndex=roomIndex, round=round)

                # add participant to room
                room.addParticipant(item)

                # add room to participant - database related
                item.roomID = room.id

            self.database.delegateParticipantToTheRoom(extendedParticipantsList=extendedParticipantsList)
            LOG.info("Participants are delegated to the rooms")
            return roomsArrayWithIndexes.getRoomArray()
        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called createGroups; Description: " + str(e))

    def createRoom(self, extendedRoom: ExtendedRoom) -> int:
        try:
            # creating room; returns roomID
            if self.communication.isInitialized() is False:
                LOG.error("Communication is not initialized")
                raise GroupManagementException("Communication is not initialized")

            if extendedRoom is None:
                LOG.error("ExtendedRoom is None")
                raise GroupManagementException("ExtendedRoom is None")

            # create supergroup - cannot be group because of admin rights
            chatID = self.communication.createSuperGroup(name=extendedRoom.roomNameShort,
                                                         description=extendedRoom.roomNameLong)

            # add participants to the room / supergroup
            for participant in extendedRoom.participants:
                self.communication.addUserToGroup(chatID=chatID, userID=participant.participant.telegramID)

            self.communication.setChatDescription(chatID=chatID, description=extendedRoom.roomNameLong)
            self.communication.promoteMembers(chatId=chatID, participants=extendedRoom.participants)
            text: str = _("Welcome to to Eden communication group! \n"
                          "This is round %d. If participant is not joined yet, send the link to the group <TODO: create link>") % \
                        (extendedRoom.round)

            self.communication.sendMessage(chatID=chatID, sessionType=SessionType.BOT, text=text)

            textPartipants: str = _("Participants in the room: \n")
            self.communication.sendMessage(chatID=chatID, sessionType=SessionType.BOT, text=textPartipants)
            for participant in extendedRoom.participants:
                self.communication.sendMessage(chatID=chatID, sessionType=SessionType.BOT, text=participant.name)

            return chatID
        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called createRoom; Description: " + str(e))

    def sendInBot(self, extendedRoom: ExtendedRoom):
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

    def groupInitialization(self, round: int, numParticipants: int, numGroups: int, isLastRound: bool = False,
                            height: int = None):
        """Starting point: Create, rename, add user to group"""
        try:
            # should be called only when state is CurrentElectionStateHandlerActive or CurrentElectionStateHandlerFinal
            LOG.info(message="should be called only when state is CurrentElectionStateHandlerActive "
                             "or CurrentElectionStateHandlerFinal")

            LOG.info("Initialization of group")

            rooms: list[ExtendedRoom] = self.getGroups(round=round, numParticipants=numParticipants,
                                                       numGroups=numGroups,
                                                       isLastRound=isLastRound,
                                                       height=height)

            for room in rooms:
                LOG.info("Room: " + str(room))
                LOG.info("Room name: " + str(room.roomNameLong))
                LOG.info("Room ID: " + str(room.id))
                LOG.info("Room participants: " + str(room.participants))
                LOG.info("Room participants count: " + str(len(room.participants)))

                # initialize names of the participants
                for participant in room.participants:
                    participant.telegramID = ADD_AT_SIGN_IF_NOT_EXISTS(participant.telegramID)

                chatID = self.createRoom(extendedRoom=room)
                room.roomTelegramID = chatID



        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException(
                "Exception thrown when called groupInitialization; Description: " + str(e))


def main():
    print("breakpoint")


if __name__ == "__main__":
    main()
