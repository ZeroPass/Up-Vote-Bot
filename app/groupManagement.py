from datetime import datetime

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from requests_unixsocket import Session

from app.chain import EdenData
from app.chain.dfuse import Response, ResponseError
#from app.chain.electionStateObjects import CurrentElectionStateHandlerActive, CurrentElectionStateHandlerFinal
from app.debugMode.modeDemo import Mode
from app.log import Log
from app.constants import eden_season, eden_year, eden_portal_url_action, telegram_bot_name, default_language, \
    admin_array, CurrentElectionState
from app.database import Database, Election, ExtendedParticipant, ExtendedRoom
from app.database.room import Room
from app.database.participant import Participant

from app.constants.rawActionWeb import RawActionWeb
from app.text.textManagement import GroupCommunicationTextManagement

from app.transmission import Communication, SessionType
from app.transmission.name import ADD_AT_SIGN_IF_NOT_EXISTS

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
        self.rooms = list[ExtendedRoom]

    def getRoom(self, roomIndex: int, round: int) -> Room:
        for room in self.rooms:
            if room.roomIndex == roomIndex and room.round == round:
                return room
        raise GroupManagementException("RoomArray.getRoom; Room not found")

    def setRooms(self, rooms: list[ExtendedRoom]):
        assert isinstance(rooms, list), "rooms must be a list"
        self.rooms = rooms

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

    def getParticipantsFromChain(self, round: int, height: int = None) -> list[ExtendedParticipant]:
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

    def getGroups(self, election: Election, round: int, numParticipants: int, numGroups: int, isLastRound: bool = False,
                  height: int = None) -> list[ExtendedRoom]:
        assert isinstance(election, Election), "election must be an Election object"
        """Create groups"""
        try:
            LOG.info("Create groups")


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
            extendedParticipantsList: list[ExtendedParticipant] = self.getParticipantsFromChain(round=round,
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

            self.database.delegateParticipantsToTheRoom(extendedParticipantsList=extendedParticipantsList)
            LOG.info("Participants are delegated to the rooms")
            return roomsArrayWithIndexes.getRoomArray()
        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called createGroups; Description: " + str(e))

    def createRoom(self, extendedRoom: ExtendedRoom) -> int:
        # everything that needs to be done when a room is created and right after that
        try:
            # creates room and returns roomID
            if self.communication.isInitialized() is False:
                LOG.error("Communication is not initialized")
                raise GroupManagementException("Communication is not initialized")

            if extendedRoom is None:
                LOG.error("ExtendedRoom is None")
                raise GroupManagementException("ExtendedRoom is None")

            # create supergroup - cannot be just a simple group because of admin rights
            chatID = self.communication.createSuperGroup(name=extendedRoom.roomNameShort,
                                                         description=extendedRoom.roomNameLong)

            # not needed because of supergroup
            # self.communication.setChatDescription(chatID=chatID, description=extendedRoom.roomNameLong)

            # add participants to the room / supergroup
            LOG.debug("Add bot to the room")
            self.communication.addChatMembers(chatID=chatID, userID=[telegram_bot_name])
            LOG.debug("Promote bot in the room to admin rights")
            self.communication.promoteMembers(sessionType=SessionType.USER, chatID=chatID, userID=[telegram_bot_name])

            #self.communication.leaveChat(sessionType=SessionType.USER, chatID=chatID) # just temporary comment out

            #
            # From this point the user bot is not allowed - bot has all rights and can do everything it needs to be done
            #

            LOG.debug("Add participants to the room")
            if self.mode == Mode.LIVE:
                self.communication.addChatMembers(chatId=chatID,
                                                  participants=extendedRoom.getMembersTelegramIDsIfKnown())
            else:
                knownTelegramIDs: list[str] = extendedRoom.getMembersTelegramIDsIfKnown()
                LOG.debug("This line printed because of test mode. Known telegram IDs: " + knownTelegramIDs)
                LOG.debug("Instead of participants, bot will working with admin_array:" + admin_array)
                self.communication.addChatMembers(chatId=chatID,
                                                  participants=admin_array)

            LOG.debug("Promote participants to admin rights")
            # make sure BOT has admin rights
            if self.mode == Mode.LIVE:
                self.communication.promoteMembers(sessionType=SessionType.BOT,
                                                  chatId=chatID,
                                                  participants=extendedRoom.getMembersTelegramIDsIfKnown())
            else:
                knownTelegramIDs: list[str] = extendedRoom.getMembersTelegramIDsIfKnown()
                LOG.debug("This line printed because of test mode. Known telegram IDs: " + knownTelegramIDs)
                LOG.debug("Instead of participants, bot will working with admin_array:" + admin_array)
                self.communication.promoteMembers(sessionType=SessionType.BOT,
                                                  chatID=chatID,
                                                  userID=admin_array)

            # initialize text management object
            gCtextManagement: GroupCommunicationTextManagement = \
                GroupCommunicationTextManagement(language=default_language)

            # get invitation link, store it in the database, share it with the participants, send it to private
            # chat with the bot

            # make sure bot has admin rights
            inviteLink: str = self.communication.getInvitationLink(sessionType=SessionType.BOT, chatID=chatID)
            if isinstance(inviteLink, str) is False:
                LOG.error("Invitation link is not valid. Not private (bot-user) message sent to the participants")
            else:
                LOG.debug(
                    "Invitation link is valid. Send private (bot-user) message to the participants. This invitation"
                    "link is valid until next call of this function! Make sure you handle it properly!")
                buttons = gCtextManagement.invitationLinkToTheGroupButons(invitationLink=inviteLink)
                for item in extendedRoom.getMembersTelegramIDsIfKnown():
                    self.communication.sendMessage(sessionType=SessionType.BOT,
                                                   chatID=item,
                                                   text=gCtextManagement.invitationLinkToTheGroup(
                                                       round=extendedRoom.round),
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
            self.communication.sendMessage(chatID=chatID,
                                           sessionType=SessionType.BOT,
                                           text=gCtextManagement.wellcomeMessage(inviteLink=inviteLink,
                                                                                 round=extendedRoom.round))

            LOG.info("Print out the room participants")
            self.communication.sendMessage(chatID=chatID,
                                           sessionType=SessionType.BOT,
                                           text=gCtextManagement.participantsInTheRoom())
            for participant in extendedRoom.participants:
                self.communication.sendMessage(chatID=chatID,
                                               sessionType=SessionType.BOT,
                                               text=gCtextManagement.participant(accountName=participant.accountName,
                                                                                 participantName=
                                                                                 participant.participantName,
                                                                                 telegramID=participant.telegramID))
            if self.mode == Mode.DEMO:
                self.communication.sendMessage(chatID=chatID,
                                               sessionType=SessionType.BOT,
                                               text=gCtextManagement.demoMessageInCreateGroup())

            LOG.info("Creating room finished")
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

    def sendNotificationTimeLeft(self, extendedRoom: ExtendedRoom, timeLeftInMinutes: int):
        try:
            assert isinstance(extendedRoom, ExtendedRoom), "extendedRoom is not an ExtendedRoom object"
            assert isinstance(timeLeftInMinutes, int), "timeLeftInMinutes is not an int object"
            assert timeLeftInMinutes > 0, "timeLeftInMinutes is not greater than 0"

            text: str = _("Only **%d minutes left** for voting in round %d. If you have not voted yet, "
                          "check the buttons bellow") % (extendedRoom.round, timeLeftInMinutes)

            inlineReplyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                inline_keyboard=
                [
                    [
                        InlineKeyboardButton(text=_("Vote on Eden members portal"),
                                             url=eden_portal_url_action),
                        InlineKeyboardButton(text=_("or on blocks.io"),  # check if specific link is possible
                                             url=RawActionWeb().electVote(round=extendedRoom.round,
                                                                          voter=None,
                                                                          candidate=None))
                    ]
                ]
            )

            self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatID=extendedRoom.roomTelegramID,
                                           text=text,
                                           inlineReplyMarkup=inlineReplyMarkup
                                           )

        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called notificationTimeLeft; Description: " + str(e))

    def groupInitialization(self, election: Election, round: int, numParticipants: int, numGroups: int,
                            isLastRound: bool = False, height: int = None):
        """Create, rename add user to group"""
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

            rooms: list[ExtendedRoom] = self.getGroups(election=Election, round=round, numParticipants=numParticipants,
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
            LOG.info("Updating rooms in the database - telegramID column")
            self.database.updateRoomsTelegramID(listOfRooms=rooms)
            self.database.updateElectionSetGroupCreatedOnTrue(election=election)



        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException(
                "Exception thrown when called groupInitialization; Description: " + str(e))

    def manage(self, round: int, numParticipants: int, numGroups: int, isLastRound: bool = False, height: int = None):
        """Staring point of the group management code"""
        # call only when CurrentElectionState is CurrentElectionStateHandlerActive or CurrentElectionStateHandlerFinal
        assert isinstance(round, int), "round is not an int object"
        assert isinstance(numParticipants, int), "numParticipants is not an int object"
        assert isinstance(numGroups, int), "numGroups is not an int object"
        assert isinstance(isLastRound, [bool, type(None)]), "isLastRound is not a bool object or None"
        assert isinstance(height, [int, type(None)]), "height is not an int object or None"

        try:
            LOG.info("Group management started")

            election: Election = self.database.getLastElection()
            if election is None:
                LOG.exception("GroupManagement.createGroups; No election found!")
                raise GroupManagementException("GroupManagement.createGroups; No election found!")

            # check if groups are already created
            if self.database.electionGroupsCreated() is False:
                LOG.info("Groups are not created yet, creating them")
                self.groupInitialization(election=election,
                                         round=round,
                                         numParticipants=numParticipants,
                                         numGroups=numGroups,
                                         isLastRound=isLastRound,
                                         height=height)
            else:
                LOG.info("Groups are already created")


        except Exception as e:
            LOG.exception("Exception thrown when called manage function; Description: " + str(e))
            raise GroupManagementException("Exception thrown when called manage function; Description: " + str(e))




def main():
    print("breakpoint")


if __name__ == "__main__":
    main()
