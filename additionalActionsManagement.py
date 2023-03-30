import asyncio
from typing import Union

import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from chain import EdenData
from database import Database, Election, ExtendedRoom
from database.room import Room
from debugMode.modeDemo import Mode, ModeDemo
from log import Log
from text.textManagement import EndOfRoundTextManagement, Button
from transmission import Communication, SessionType
from transmission.Communication import CustomMember


# This class is used to do additional actions at the end of the elections like:
# - Cleaning unused groups/channels
# - Removing the bot and user bot from used the groups/channels

class AfterEveryRoundAdditionalActionsException(Exception):
    pass

class FinalRoundAdditionalActionsException(Exception):
    pass


class AdditionalActionManagementException(Exception):
    pass

LOG_aeraa = Log(className="AfterEveryRoundAdditionalActions")
LOG_fraa = Log(className="FinalRoundAdditionalActions")
LOG = Log(className="AdditionalActionManagement")


class AfterEveryRoundAdditionalActions:
    def __init__(self, election: Election, edenData: EdenData, database: Database, communication: Communication,
                 modeDemo: ModeDemo):
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(edenData, EdenData), "edenData is not an EdenData object"
        assert isinstance(database, Database), "database is not a Database object"
        assert isinstance(communication, Communication), "communication is not a Communication object"
        assert isinstance(modeDemo, ModeDemo), "modeDemo is not a ModeDemo object"
        self.election = election
        self.edenData = edenData
        self.database = database
        self.communication = communication
        self.modeDemo = modeDemo
        LOG_aeraa.log("AfterEveryRoundAdditionalActions object created")

    def isVideoCallRunning(self, chatId: Union[int, str]):
        try:
            isRunning = asyncio.get_event_loop().run_until_complete(self.communication.isVideoCallRunning(
                                                                        sessionType=SessionType.BOT,
                                                                        chatId=chatId))

            LOG_aeraa.debug("Is video call running: " + str(isRunning) + " in chat " + str(chatId))
            if isRunning is None:
                return LOG_aeraa.error("Error while getting information if video call is active. Return False")
                return False
            return isRunning
        except Exception as e:
            LOG_aeraa.exception("Error while getting information if video call is active: " + str(e))
            return False

    def getGroupsInRound(self, round: int, predisposedBy: str) -> list[Room]:
        assert isinstance(round, int), "round is not an integer"
        assert isinstance(predisposedBy, str), "predisposedBy is not a string"
        try:
            rooms = self.database.getRoomsElectionFilteredByRound(election=self.election,
                                                                  round=round,
                                                                  predisposedBy=predisposedBy)
            if rooms is None or len(rooms) == 0:
                LOG_aeraa.error("No rooms (predisposed by: " + predisposedBy + ") found for round " + str(round))
                return None
            return rooms
        except Exception as e:
            LOG_aeraa.exception("Error while getting rooms for round " + str(round) + ": " + str(e))
            return None

    def videoCallStillRunningSendMsg(self, room: Room):
        assert isinstance(room, Room), "room is not a Room object"
        try:
            LOG_aeraa.debug("Video call is still running in group " + str(room.roomID) + ". Sending message")
            endOfRoundTextManagement: EndOfRoundTextManagement = EndOfRoundTextManagement()

            photoPath: str = endOfRoundTextManagement.endVideoChatImagePath()
            text: str = endOfRoundTextManagement.roundIsOverAndVideoIsRunning()

            result: bool =self.communication.sendPhoto(sessionType=SessionType.BOT,
                                         chatId=room.roomTelegramID,
                                         photoPath=photoPath,
                                         caption=text)

            LOG_aeraa.debug("Last message to group(video stil running) sent to room " + str(room.roomID) +
                      ". Result: " + str(result))
        except Exception as e:
            LOG_aeraa.exception("Error while sending message to room " + str(room.roomID) + ": " + str(e))

    def roundEndMsg(self, room: Room):
        assert isinstance(room, Room), "room is not a Room object"
        try:
            LOG_aeraa.debug("Video call is still running in group " + str(room.roomID) + ". Sending message")
            endOfRoundTextManagement: EndOfRoundTextManagement = EndOfRoundTextManagement()

            text: str = endOfRoundTextManagement.roundIsOverAndVideoIsNotRunning()

            button: Button = endOfRoundTextManagement.roundIsOverButton(
                inviteLink=endOfRoundTextManagement.roundIsOverUploadVideoLink())
            replyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=button['text'],
                            url=button['value']
                        )
                    ]
                ]
            )
            result: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatId=room.roomTelegramID,
                                           text=text,
                                           replyMarkup=replyMarkup)
            LOG_aeraa.debug("Last message to group sent to room " + str(room.roomID) + ". Result: " + str(result))
        except Exception as e:
            LOG_aeraa.exception("Error while sending message to room " + str(room.roomID) + ": " + str(e))

    def removingBotFromGroupsAndDeleteUnusedGroups(self, round: int,  telegramBotName: str, telegramUserBotName: str):
        assert isinstance(round, int), "round is not an integer"
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        try:
            LOG_aeraa.log("Removing the bot from groups")
            rooms: list[Room] = self.getGroupsInRound(round=round, predisposedBy=telegramUserBotName)

            if rooms is None or len(rooms) == 0:
                LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                " No rooms found")
                return

            for room in rooms:
                try:
                    # we want to get actual members in the group, not the ones in the database
                    members: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.BOT,
                                                                                       chatId=room.chatId)
                    if len(members) == 0:
                        LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                       " Requested as bot. No members found in the group " + str(room.chatId))

                        members: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.USER,
                                                                                           chatId=room.chatId)
                        if len(members) == 0:
                            LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                           " Requested as user. No members found in the group " + str(room.chatId))
                    counterUsers = 0
                    for member in members:
                        # bots are not counted
                        if member.isBot:
                            continue
                        # user bot is not counted
                        if member.username == telegramUserBotName:
                            continue
                        if member.username == telegramBotName:
                            # probably never happens, because of .isBot check before
                            continue
                        counterUsers += 1

                    # if no users are found in the group, the group will be deleted!
                    if counterUsers == 0:
                        LOG_aeraa.log("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: "
                                      "No users found in the group " + str(room.chatId) + ". Removing the group")
                        response: bool = self.communication.deleteGroup(chatId=room.chatId)
                        if response:
                            self.database.archiveRoom(room=room)
                        LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                        " archiveRoom with id " + str(room.chatId + " done"))
                    else:
                        LOG_aeraa.log("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: "
                                      "Removing the bot from the group " + str(room.chatId))
                        response: bool = self.communication.leaveChat(sessionType=SessionType.BOT,
                                                                      chatId=room.chatId,
                                                                      userId=telegramBotName)
                        LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                        "Is bot left chat with id " + str(room.chatId + " done? " + str(response)))

                        response: bool = self.communication.leaveChat(sessionType=SessionType.USER,
                                                                      chatId=room.chatId,
                                                                      userId=telegramUserBotName)
                        LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                        "Is USER-bot left chat with id " + str(room.chatId + " done? " + str(response)))
                        if response is False:
                            LOG_aeraa.error("Error while removing USER_BOT(" + telegramUserBotName + ") from the group "
                                           + str(room.chatId))
                except Exception as e:
                    LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups.inner "
                                    "exp: Error while removing the bot from the group or deleting unused groups"
                                    + str(room.chatId) + ": " + str(e))

        except Exception as e:
            raise AfterEveryRoundAdditionalActionsException("Error while removing the bot from groups: " + str(e))

    def checkIfVideoCallIsRunningAndGoodbyeMsg(self, election: Election, round: int, predisposedBy: str):
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(round, int), "round is not an integer"
        assert isinstance(predisposedBy, str), "predisposedBy is not a string"
        try:
            rooms: list[Room] = self.getGroupsInRound(round=round, predisposedBy=predisposedBy)
            if rooms is None or len(rooms) == 0:
                LOG.error("No rooms found. Something went wrong. Skipping additional actions")
                return
            for room in rooms:
                Log.info("Checking room: " + str(room.roomID) + ", tgID:" + str(room.roomTelegramID))
                if self.isVideoCallRunning(chatId=room.chatId):
                    LOG.debug("Video call is running in group " + str(room.chatId) + ". Stopping it")
                    self.videoCallStillRunningSendMsg(room=room)
                else:
                    self.roundEndMsg(room=room)
                    LOG.debug("Video call is not running in group " + str(room.chatId))
        except Exception as e:
            LOG_aeraa.exception("Error in checkIfVideoCallIsRunningAndGoodbyeMsg: " + str(e))

    def do(self, election: Election, round: int, telegramUserBotName: str, telegramBotName: str):
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(round, int), "round is not an integer"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        try:
            self.checkIfVideoCallIsRunningAndGoodbyeMsg(election=election,
                                                        round=round,
                                                        predisposedBy=telegramUserBotName)
            self.removingBotFromGroupsAndDeleteUnusedGroups(round=round,
                                                            telegramUserBotName=telegramUserBotName,
                                                            telegramBotName=telegramBotName)
        except Exception as e:
            LOG_aeraa.exception("Error in AfterEveryRoundAdditionalActions.do: " + str(e))
            raise AfterEveryRoundAdditionalActionsException("Error while doing additional actions: " + str(e))

    def doAfterSomeTimeRunsOut(self):
        #TODO: imlement actions after some time runs out, to send message about running video call after 10 minutes
        pass
class FinalRoundAdditionalActions:
    def __init__(self, election: Election, edenData: EdenData, database: Database, communication: Communication,
                 modeDemo: ModeDemo):
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(edenData, EdenData), "edenData is not an EdenData object"
        assert isinstance(database, Database), "database is not a Database object"
        assert isinstance(communication, Communication), "communication is not a Communication object"
        assert isinstance(modeDemo, ModeDemo), "mode is not a ModeDemo object"
        self.election = election
        self.edenData = edenData
        self.database = database
        self.communication = communication
        self.modeDemo = modeDemo
        LOG_fraa.log("FinalRoundAdditionalActions object created")

    def do(self, telegramBotName: str, telegramUserBotName: str, excludedRoom: Room):
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        assert isinstance(excludedRoom, (Room, ExtendedRoom)), "excludedRoom is not a Room or ExtendedRoom object"
        try:
            self.removingBotFromGroupsAndDeleteUnusedGroups(telegramBotName=telegramBotName,
                                                            telegramUserBotName=telegramUserBotName,
                                                            excludedRoom=excludedRoom)
        except Exception as e:
            raise FinalRoundAdditionalActionsException("Error while doing additional actions: " + str(e))

    def removingBotFromGroupsAndDeleteUnusedGroups(self, telegramBotName: str, telegramUserBotName: str,
                                                   excludedRoom: Room):
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        assert isinstance(excludedRoom, (Room, ExtendedRoom)), "excludedRoom is not a Room or ExtendedRoom object"
        try:
            LOG_fraa.log("Removing the bot from groups")
            rooms: list[Room] = self.database.getAllRoomsByElection(election=self.election,
                                                                    predisposedBy=telegramUserBotName)

            if rooms is None or len(rooms) == 0:
                LOG_fraa.error("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: No rooms found")
                return

            for room in rooms:
                try:
                    members: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.BOT,
                                                                                       chatId=room.chatId)
                    if len(members) == 0:
                        LOG_fraa.error("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                       " Requested as bot. No members found in the group " + str(room.chatId))

                        members: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.USER,
                                                                                           chatId=room.chatId)
                        if len(members) == 0:
                            LOG_fraa.error("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                           " Requested as user. No members found in the group " + str(room.chatId))
                    counterUsers = 0
                    for member in members:
                        # bots are not counted
                        if member.isBot:
                            continue
                        # user bot is not counted
                        if member.username == telegramUserBotName:
                            continue
                        if member.username == telegramBotName:
                            # probably never happens, because of .isBot check before
                            continue
                        counterUsers += 1

                    # if no users are found in the group, the group is deleted, only LAST GROUP is not deleted, just
                    # remove users!
                    if counterUsers == 0 and room.chatId != excludedRoom.chatId:
                        LOG_fraa.log("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: "
                                     "No users found in the group " + str(room.chatId) + ". Removing the group")
                        self.communication.deleteGroup(chatId=room.chatId)
                        self.database.archiveRoom(room=room)
                        LOG_fraa.debug("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                       " archiveRoom with id " + str(room.chatId + " done"))
                    else:
                        LOG_fraa.log("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: "
                                     "Removing the bot from the group " + str(room.chatId))
                        response: bool = self.communication.leaveChat(sessionType=SessionType.BOT,
                                                                      chatId=room.chatId,
                                                                      userId=telegramBotName)
                        LOG_fraa.debug("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                       "Is bot leaving chat with id " + str(room.chatId + " done? " + str(response)))

                        response: bool = self.communication.leaveChat(sessionType=SessionType.USER,
                                                                      chatId=room.chatId,
                                                                      userId=telegramUserBotName)
                        LOG_fraa.debug("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                       "Is USER bot leaving chat with id " + str(
                            room.chatId + " done? " + str(response)))
                        if response is False:
                            LOG_fraa.error("Error while removing USER_BOT(" + telegramUserBotName + ") from the group "
                                           + str(room.chatId))
                except Exception as e:
                    LOG_fraa.error("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups.inner exp: "
                                   "Error while removing the bot from the group or deleting unused groups"
                                   + str(room.chatId) + ": " + str(e))

        except Exception as e:
            raise FinalRoundAdditionalActionsException("Error while removing the bot from groups: " + str(e))


#
# This class is used to manage the additional actions of the bot.
#

class AdditionalActionManagement:
    def __init__(self, additionalActions):
        self.additionalActions = additionalActions
