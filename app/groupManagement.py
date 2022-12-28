from datetime import datetime, timedelta

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from requests_unixsocket import Session

from app.chain import EdenData
from app.chain.dfuse import Response, ResponseError
# from app.chain.electionStateObjects import CurrentElectionStateHandlerActive, CurrentElectionStateHandlerFinal
from app.debugMode.modeDemo import Mode, ModeDemo
from app.log import Log
from app.constants import eden_season, eden_year, eden_portal_url_action, telegram_bot_name, default_language, \
    telegram_admins_id, CurrentElectionState, start_video_preview_path, ReminderGroup, \
    time_span_for_notification_time_is_up, telegram_user_bot_name
from app.database import Database, Election, ExtendedParticipant, ExtendedRoom, Reminder, ReminderSent, database
from app.database.room import Room
from app.database.participant import Participant

from app.constants.rawActionWeb import RawActionWeb
from app.text.textManagement import GroupCommunicationTextManagement

from app.dateTimeManagement.dateTimeManagement import DateTimeManagement

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
        raise GroupManagementException("RoomArray.getRoom; Room not found")

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

    def createPredefinedGroupsIfNeeded(self, dateTimeManagement: DateTimeManagement, numberOfGroups: int,
                                       duration: timedelta,
                                       totalGroups: int):
        """Create groups that will be ready when election is in progress
            - numberOfGroups: how many groups you want to create
            - duration: time between creating new groups , probably the best would be every 24 hours
            - how many groups in total should be prepared before election
            """

        try:
            assert isinstance(dateTimeManagement,
                              DateTimeManagement), "dateTimeManagement must be an DateTimeManagementObject"
            assert isinstance(numberOfGroups, int), "numberOfGroups must be an int"
            assert isinstance(duration, timedelta), "duration variable must be timedelta"
            assert isinstance(totalGroups, int), "totalGroups variable must be an int"

            LOG.debug("Create predefined groups; number of groups" + str(numberOfGroups) +
                      ", total groups: " + str(totalGroups) + ", duration: " + str(duration))

            dummyElectionForFreeRooms: Election = self.database.getLastElection(freeRoomElection=True)
            if dummyElectionForFreeRooms is None:
                raise GroupManagementException("No dummy election set in database")

            # rooms are sorted by creating time
            predefinedRooms: list[Room] = self.database.getRoomsPreelection(election=dummyElectionForFreeRooms,
                                                                            predisposedBy=telegram_user_bot_name)

            if predefinedRooms is None:
                raise GroupManagementException("Something is wrong with getting predefined rooms query")

            if len(predefinedRooms) > totalGroups:
                LOG.success("Already enough groups created; number of grups:" + str(len(predefinedRooms)))
                return

            if 0 <= len(predefinedRooms) < totalGroups:
                LOG.debug("Current predefined rooms counter is between 0 and max number of groups.")
                currentDT: datetime = dateTimeManagement.getTime()

                isEmpty: bool = len(predefinedRooms) == 0
                isTimeForNewIteration: bool = len(predefinedRooms) > 0 and \
                                              predefinedRooms[0].predisposedDateTime + duration < currentDT

                if isEmpty or isTimeForNewIteration:
                    LOG.debug("Create new groups. Enough time has passed since last creation")
                    nmOfGroupLeft: int = totalGroups - len(predefinedRooms)
                    numOfGroupsToCreate: int = min(nmOfGroupLeft, numberOfGroups)
                    LOG.info("Number of groups to create:" + str(numOfGroupsToCreate))

                    if self.communication.isInitialized is False:
                        LOG.error("Communication is not initialized")
                        raise GroupManagementException("Communication is not initialized")

                    extendedRooms: list[ExtendedRoom] = []
                    for i in range(numOfGroupsToCreate):
                        try:
                            shortName: str = "Up Vote Election Bot - " + currentDT.isoformat()
                            longName: str = "Pre-created group for upcoming Election; Up Vote Election Bot - " + \
                                            currentDT.isoformat()
                            # create supergroup - cannot be just a simple group because of admin rights
                            chatID = self.communication.createSuperGroup(name=shortName,
                                                                         description=longName)
                            if chatID is None:
                                LOG.exception("ChatID is None")
                                raise GroupManagementException("ChatID is None")

                            # updating telegramID in database
                            self.communication.addKnownUserAndUpdateLocal(botName=telegram_bot_name, chatID=str(chatID))
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
                                                              roomIndex=-1,
                                                              roomNameShort=shortName,
                                                              roomNameLong=longName,
                                                              round=-1,
                                                              roomTelegramID=str(chatID),
                                                              shareLink=inviteLink
                                                              )
                            extendedRooms.append(room)

                        except Exception as e:
                            LOG.exception("Exception thrown when called GroupManagement.createPredefinedGroups.forLoop"
                                          " Description: " + str(e))

                    if len(extendedRooms) > 0:
                        self.database.createRooms(listOfRooms=extendedRooms)
                        LOG.success("Rooms are successfully saved in database")
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

    def getFreePreelectionRoom(self, predisposedBy: str):
        try:
            assert isinstance(predisposedBy, str), "predisposedBy must be str"
            # get pre-election
            election: Election = self.database.getLastElection(freeRoomElection=True)
            if election is None:
                raise GroupManagementException("getFreePreelectionRoom; Pre-election not found")

            rooms: list[Room] = self.database.getRoomsPreelection(election=election,
                                                                  predisposedBy=predisposedBy)
            if rooms is None or len(rooms) == 0:
                LOG.error("getFreePreelectionRoom; No free room found under username: " + predisposedBy +
                          " You need to create new room live.")
                return None

            # return the oldest group/name if it is correct format
            if isinstance(rooms[0], Room):
                return rooms[0]
            else:
                LOG.error("getFreePreelectionRoom; First element is not type of Room")
                return None
        except Exception as e:
            raise GroupManagementException(
                "Exception thrown when called GroupManagement.getParticipantsFromChain; Description: " + str(e))

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
            # TODO find the way to use already created groups
            roomArrayNewGroups: RoomArray = RoomArray()
            roomArrayPrecreatedGroups: RoomArray = RoomArray()
            for index in range(numGroups):  # from 0 to numGroups -1
                if self.database.isGroupCreated(election=election,
                                                round=round,
                                                roomIndex=index):
                    LOG.debug("Room with electionID: " + str(election.electionID) + ", round:" + str(round) +
                              ", room index:" + str(index) + "already exists")
                    continue

                else:
                    room: Room = self.getFreePreelectionRoom(predisposedBy=telegram_user_bot_name)

                    # get the name of the group
                    roomName: RoomName = RoomName(round=round,
                                                  roomIndex=index,
                                                  season=eden_season,
                                                  year=eden_year,
                                                  isLastRound=isLastRound)

                    if room is not None:
                        LOG.debug("Free (created in the past) room found. RoomID: " + str(room.roomID))
                        extendedRoom: ExtendedRoom = ExtendedRoom.fromRoom(room=room)

                        # change to real parameters (election, index, name)
                        extendedRoom.electionID = election.electionID
                        extendedRoom.roomIndex = index
                        extendedRoom.round = round
                        extendedRoom.roomNameLong = roomName.nameLong()
                        extendedRoom.roomNameShort = roomName.nameShort()
                        self.database.updatePreCreatedRoom(room=extendedRoom)

                        # add to the set of groups to update in database
                        roomArrayPrecreatedGroups.setRoom(extendedRoom)
                    else:
                        LOG.debug("Free (created in the past) room NOT found. Create new one")
                        room: ExtendedRoom = ExtendedRoom(electionID=election.electionID,
                                                          round=round,
                                                          roomIndex=index,
                                                          roomNameLong=roomName.nameLong(),
                                                          roomNameShort=roomName.nameShort())

                        roomArrayNewGroups.setRoom(room)

            LOG.debug("Number of rooms to change bio: " + str(roomArrayPrecreatedGroups.numRooms()))
            LOG.debug("Number of rooms to create: " + str(roomArrayNewGroups.numRooms()))

            LOG.info("Writing rooms (that needs to be created) in database and getting their indexes")
            roomsListWithIndexes = self.database.createRooms(listOfRooms=roomArrayNewGroups.getRoomArray())
            roomArrayBothMerged: RoomArray = RoomArray()
            roomArrayBothMerged.setRooms(roomsListWithIndexes)
            roomArrayBothMerged.appendRooms(rooms=roomArrayPrecreatedGroups.getRoomArray())
            LOG.info("... room creation finished. Rooms are set with IDs in database.")


            #updated one by one: because of getFreePreelectionRoom function - other way it found always same room
            #LOG.info("Updating rooms (that needs to be update) in database(electionID, roomIndex, names")
            #self.database.updatePreCreatedRooms(listOfRooms=roomArrayPrecreatedGroups.getRoomArray())

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

                # add participant to room
                room.addMember(item)

                # add room to participant - database related
                item.roomID = room.roomID

            preelectionRoom: Room = self.database.getRoomWithAllUsersBeforeElection(election=election)
            if preelectionRoom is None:
                raise GroupManagementException("Preelection room is not set in database")
            self.database.delegateParticipantsToTheRoom(extendedParticipantsList=extendedParticipantsList,
                                                        roomPreelection=preelectionRoom)
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

            if extendedRoom.roomTelegramID is None or extendedRoom.roomTelegramID == "":
                # create supergroup - cannot be just a simple group because of admin rights
                chatID = self.communication.createSuperGroup(name=extendedRoom.roomNameShort,
                                                             description=extendedRoom.roomNameLong)
                if chatID is None:
                    LOG.exception("ChatID is None")
                    raise GroupManagementException("ChatID is None")
                extendedRoom.roomTelegramID = str(chatID)
                self.database.updateRoomTelegramID(room=extendedRoom)
            else:
                chatID = int(extendedRoom.roomTelegramID)
                self.communication.setChatTitle(chatId=chatID, title=extendedRoom.roomNameShort)
                self.communication.setChatDescription(chatId=chatID, description=extendedRoom.roomNameLong)

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
            if self.mode == Mode.LIVE:  # or True always add participants to the room - not admins
                self.communication.addChatMembers(chatId=chatID,
                                                  participants=membersWithInteractionWithCurrentBot)
            else:
                knownTelegramIDs: list[str] = extendedRoom.getMembersTelegramIDsIfKnown()
                LOG.debug("This line printed because of test mode. Known telegram IDs: " + str(knownTelegramIDs))
                LOG.debug(
                    "Instead of participants, bot will working with telegram_admins_id:" + str(telegram_admins_id))
                self.communication.addChatMembers(chatId=chatID,
                                                  participants=telegram_admins_id)

            # LOG.debug("Add participants to the room - database related")
            # check if needed self.database.delegateParticipantsToTheRoom(extendedParticipantsList=extendedRoom.getMembers(),

            LOG.debug("Promote participants to admin rights")
            # make sure BOT has admin rights
            if self.mode == Mode.LIVE:  # or True always promote participants in the room - not admins
                self.communication.promoteMembers(sessionType=SessionType.BOT,
                                                  chatId=chatID,
                                                  participants=membersWithInteractionWithCurrentBot)
            else:
                knownTelegramIDs: list[str] = extendedRoom.getMembersTelegramIDsIfKnown()
                LOG.debug("This line printed because of test mode. Known telegram IDs: " + str(knownTelegramIDs))
                LOG.debug(
                    "Instead of participants, bot will working with telegram_admins_id:" + str(telegram_admins_id))
                self.communication.promoteMembers(sessionType=SessionType.BOT,
                                                  chatId=chatID,
                                                  participants=telegram_admins_id)

            # initialize text management object
            gCtextManagement: GroupCommunicationTextManagement = \
                GroupCommunicationTextManagement(language=default_language)

            # get invitation link, store it in the database, share it with the participants, send it to private
            # chat with the bot

            # make sure bot has admin rights
            if extendedRoom.shareLink is None or extendedRoom.shareLink == '':
                inviteLink: str = self.communication.getInvitationLink(sessionType=SessionType.USER, chatId=chatID)
            else:
                inviteLink = extendedRoom.shareLink

            if isinstance(inviteLink, str) is False:
                LOG.error("Invitation link is not valid. Not private (bot-user) message sent to the participants")
            else:
                LOG.debug(
                    "Invitation link is valid. Send private (bot-user) message to the participants. This invitation"
                    "link is valid until next call of this function! Make sure you handle it properly!")
                buttons = gCtextManagement.invitationLinkToTheGroupButons(inviteLink=inviteLink)

                # send private message to the participants, in case of test mode to the admins
                if self.mode == Mode.LIVE:  # or True always send invitation link to the participants - not admins
                    members = extendedRoom.getMembersTelegramIDsIfKnown()
                else:
                    # demo mode
                    members = telegram_admins_id

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
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called createRoom; Description: " + str(e))

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

    """def sendNotificationTimeLeftIfNeeded(self, extendedRoom: ExtendedRoom, round: int, modeDemo: ModeDemo):
        try:
            assert isinstance(extendedRoom, ExtendedRoom), "extendedRoom is not an ExtendedRoom object"
            assert isinstance(round, int), "round is not an int object"
            assert round > 0, "round is not greater than 0"

            executionTime: datetime = self.setExecutionTime(modeDemo=modeDemo)
            reminders = self.database.getReminders(election=extendedRoom.electionID,
                                                   reminderGroup=ReminderGroup.IN_ELECTION)

            if reminders is not None:
                for item in reminders:
                    if isinstance(item, Reminder):
                        reminder: Reminder = item
                        LOG.info("Reminder: " + str(reminder))
                        LOG.debug("Reminder time: " + str(reminder.dateTimeBefore) +
                                  "; Reminder time span: " + str(reminder.dateTimeBefore + timedelta(
                            minutes=time_span_for_notification_time_is_up)) +
                                  " ..."
                                  )

                        if reminder.dateTimeBefore < executionTime < reminder.dateTimeBefore + timedelta(
                                minutes=time_span_for_notification_time_is_up):
                            LOG.info("... send reminder to election id: " + str(reminder.electionID) +
                                     " and dateTimeBefore: " + str(reminder.dateTimeBefore))
                            #members: list[Participant] = self.database.getMembersInElectionRoundNotYetSend(election=election)
                            reminderSentList: list[ReminderSent] = self.database.getAllParticipantsReminderSentRecord(
                                reminder=reminder)
                            for member in extendedRoom.members:
                                if member.telegramID is None or len(member.telegramID) < 3:
                                    LOG.debug("Member " + str(member) + " has no known telegramID, skip sending")
                                    continue

                                isSent: bool = self.sendAndSyncWithDatabaseElectionIsComing(member=member,
                                                                                            election=election,
                                                                                            reminder=reminder,
                                                                                            reminderSentList=reminderSentList,
                                                                                            modeDemo=modeDemo)
                                if isSent:
                                    LOG.info("Reminder (for user: " + member.accountName + " sent to telegramID: "
                                             + member.telegramID)

                        else:
                            LOG.debug("... reminder is not needed!")

            else:
                LOG.error("Reminders are not set in the database. Something went wrong.")


            ##############################
            textManagement: GroupCommunicationTextManagement = GroupCommunicationTextManagement(
                language=default_language)

            # send notification to the room
            text: str = textManagement.timeIsAlmostUpGroup(timeLeftInMinutes=timeLeftInMinutes,
                                                           round=extendedRoom.round)

            buttonText: tuple[str] = textManagement.timeIsAlmostUpButton()

            if len(buttonText) != 2:
                LOG.error("Button text is not valid")
                raise GroupManagementException("Button text is not valid")

            inlineReplyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                inline_keyboard=
                [
                    [
                        InlineKeyboardButton(text=buttonText[0],
                                             url=eden_portal_url_action)
                    ]
                ]

            )

            self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatID=extendedRoom.roomTelegramID,
                                           text=text,
                                           inlineReplyMarkup=inlineReplyMarkup
                                           )

            # send notification to the participants

            textParticipant: str = textManagement.timeIsAlmostUpGroup(timeLeftInMinutes=timeLeftInMinutes,
                                                                      round=extendedRoom.round)

            for participant in extendedRoom.participants:
                inlineReplyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                    inline_keyboard=
                    [
                        [
                            InlineKeyboardButton(text=buttonText[0],
                                                 url=eden_portal_url_action),
                            InlineKeyboardButton(text=buttonText[1],  # check if specific link is possible
                                                 url=RawActionWeb().electVote(round=extendedRoom.round,
                                                                              voter=None,
                                                                              candidate=None))
                        ]
                    ]
                )

                self.communication.sendMessage(sessionType=SessionType.BOT,
                                               chatID=participant.telegramID,
                                               text=text,
                                               inlineReplyMarkup=inlineReplyMarkup
                                               )
        #################
        except Exception as e:
            LOG.exception(str(e))
            raise GroupManagementException("Exception thrown when called notificationTimeLeft; Description: " + str(e))
    """

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
        assert isinstance(isLastRound, (bool, type(None))), "isLastRound is not a bool object or None"
        assert isinstance(height, (int, type(None))), "height is not an int object or None"

        try:
            LOG.info("Group management started")

            election: Election = self.database.getLastElection()
            if election is None:
                LOG.exception("GroupManagement.createGroups; No election found!")
                raise GroupManagementException("GroupManagement.createGroups; No election found!")

            # check if groups are already created
            if self.database.electionGroupsCreated(election=election,
                                                   round=round,
                                                   numRooms=numGroups) is False:
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
