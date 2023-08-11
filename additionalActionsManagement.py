import asyncio
from datetime import datetime, timedelta
from typing import Union

import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from chain import EdenData
from chain.stateElectionState import ElectCurrTable
from constants import telegram_bot_name
from database import Database, Election, ExtendedRoom
from database.election import ElectionRound
from database.participant import Participant
from database.room import Room
from debugMode.modeDemo import Mode, ModeDemo
from log import Log
from text.textManagement import EndOfRoundTextManagement, Button
from transmission import Communication, SessionType
from transmissionCustom import CustomMember

from transmissionCustom import REMOVE_AT_SIGN_IF_EXISTS


# This class is used to do additional actions at the end of the elections like:
# - Cleaning unused groups/channels
# - Removing the bot and user bot from used the groups/channels

class AfterElectionAdditionalActionsException(Exception):
    pass

class AfterEveryRoundAdditionalActionsException(Exception):
    pass

class FinalRoundAdditionalActionsException(Exception):
    pass


class AdditionalActionManagementException(Exception):
    pass
LOG_aeaa = Log(className="AfterElectionAdditionalActions")
LOG_aeraa = Log(className="AfterEveryRoundAdditionalActions")
LOG_fraa = Log(className="FinalRoundAdditionalActions")
LOG = Log(className="AdditionalActionManagement")


class AfterElectionAdditionalActions:
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
        self.executionTime = self.setExecutionTime(modeDemo=modeDemo)
        LOG_aeaa.debug("AfterElectionAdditionalActions object created")

    def setExecutionTime(self, modeDemo: ModeDemo = None) -> datetime:
        """Set execution time; if modeDemo is defined then use datetime from modeDemo.blockHeight
        otherwise
        use time of the node as main time of server"""
        if modeDemo is None:
            # in live mode time of blockchain is also time of server
            blockchainTime: datetime = self.dateTimeManagement.getTime()
            return blockchainTime
        else:
            # in demo mode time of block is also time of server
            blockchainTime: datetime = modeDemo.getCurrentBlockTimestamp()
            return blockchainTime

    def isInTimeframe(self, executionTime: datetime, electionDate: datetime, deadlineInMinutes: int,
                      executionTimeframeInMinutes: int) -> bool:
        """Check if it is time to do an action"""
        try:
            assert isinstance(executionTime, datetime), "executionTime is not instance of datetime"
            assert isinstance(electionDate, datetime), "electionDate is not instance of datetime"
            assert isinstance(deadlineInMinutes, int), "deadlineInMinutes is not instance of int"
            assert isinstance(executionTimeframeInMinutes, int), "executionTimeframeInMinutes is not instance of int"

            LOG.trace("Check if it is time to do action. "
                      "executionTime: " + str(executionTime) +
                      ", electionDate: " + str(electionDate) +
                      ", deadlineInMinutes: " + str(deadlineInMinutes) +
                      ", executionTimeframeInMinutes: " + str(executionTimeframeInMinutes)
                      )

            lowerEnd: datetime = electionDate + timedelta(minutes=deadlineInMinutes)
            higherEnd: datetime = lowerEnd + timedelta(minutes=executionTimeframeInMinutes)

            if  executionTime>= lowerEnd and executionTime <= higherEnd:
                LOG.info("We are in the timeframe to do action")
                return True
            else:
                LOG.info("We are NOT in the timeframe to do action")
                return False
        except Exception as e:
            LOG.exception("Exception (in isInTimeframe): " + str(e))
            raise AfterElectionAdditionalActionsException("Exception (in isInTimeframe): " + str(e))

    def getRoomsFromDatabase(self, election: Election, predisposedBy: str) -> list[Room]:
        """Get participants from database"""
        try:
            assert isinstance(election, Election), "election is not an Election object"
            assert isinstance(predisposedBy, str), "predisposedBy is not an str object"
            LOG.info("Get members from database")
            rooms: list[Room] = self.database.getAllRoomsByElection(election=election, predisposedBy=predisposedBy)
            if rooms is not None:
                return rooms
            else:
                raise Exception("Participants are not set in the database. Something went wrong.")
                return None
        except Exception as e:
            LOG.exception("Exception thrown when called getRoomsFromDatabase; Description: " + str(e))
            raise AfterElectionAdditionalActionsException("Exception thrown when called getRoomsFromDatabase; Description: " + str(e))

    def getCDroomFromDatabase(self, election: Election, predisposedBy: str) -> list[Room]:
        """Get participants from database"""
        try:
            assert isinstance(election, Election), "election is not an Election object"
            assert isinstance(predisposedBy, str), "predisposedBy is not an str object"
            LOG.info("Get members from database")
            rooms: list[Room] = \
                self.database.getRoomsElectionFilteredByRound(election=election,
                                                              round=ElectionRound.FINAL.value,
                                                              predisposedBy=predisposedBy)
            if rooms is not None:
                return rooms
            else:
                raise Exception("Participants are not set in the database. Something went wrong.")
                return None
        except Exception as e:
            LOG.exception("Exception thrown when called getCDroomFromDatabase; Description: " + str(e))
            raise AfterElectionAdditionalActionsException("Exception thrown when called getCDroomFromDatabase; Description: " + str(e))


    def leavingTheRoom(self, sessionType: SessionType, room: Room)-> bool:
        """Leave the room"""
        try:
            assert isinstance(sessionType, SessionType), "sessionType is not an SessionType object"
            assert isinstance(room, Room), "room is not an Room object"
            LOG.info("Leaving the room")
            if room.roomTelegramID is None:
                LOG.error("room.roomTelegramID is None. Something went wrong when getting the room from database.")
                return

            if self.communication.isInChat(sessionType=sessionType, chatId=room.roomTelegramID) is True:
                response: bool = self.communication.leaveChat(sessionType=sessionType, chatId=room.roomTelegramID)
                if response is True:
                    LOG.info("Bot left the room")
                    return True
                else:
                    LOG.error("Bot did not leave the room or not in the room")
                    return False

            else:
                LOG.info("Bot is not in the room or check failed")
                return False
        except Exception as e:
            LOG.exception("Exception thrown when called leavingTheRoom; Description: " + str(e))
            raise AfterElectionAdditionalActionsException("Exception thrown when called leavingTheRoom; Description: " + str(e))

    def removeBotFromGroupAfterElectionAfterDefinedMinutes(self, executionTime: datetime,
                                        previousElection: Election,
                                        deadlineInMinutes: int,
                                        electCurr: ElectCurrTable,
                                        telegramBotName: str,
                                        telegramUserBotName: str):
        assert isinstance(executionTime, datetime), "executionTime is not a datetime object"
        assert isinstance(previousElection, Election), "currentElection is not an Election object"
        assert isinstance(deadlineInMinutes, int), "deadlineInMinutes is not an integer"
        assert isinstance(electCurr, ElectCurrTable), "electCurr is not an ElectCurrTable object"
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        try:
            LOG_aeaa.debug("In removeBotFromGroupAfterElection")
            if self.isInTimeframe(executionTime=executionTime,
                                 electionDate=electCurr.getLastElectionTime(),
                                 deadlineInMinutes=deadlineInMinutes,
                                 executionTimeframeInMinutes=60) is False:
                LOG_aeaa.debug("It is not time to remove bot from groups. Do not do anything")
                return

            LOG.info("... is between time span for notification. Send it if not sent yet")
            # get all rooms from database for previous election
            rooms: list[Room] = self.getRoomsFromDatabase(election=previousElection,
                                                          predisposedBy=telegramUserBotName)

            for room in rooms:
                LOG.info("Removing bot from room: " + str(room.roomID))
                if room.isArchived is True:
                    LOG.info("Room is already archived. Do not do anything")
                    continue
                LOG.info("Removing bot from room: " + str(room.roomID))
                isArchived: bool = self.leavingTheRoom(sessionType=SessionType.BOT, room=room)
                if isArchived is True:
                    LOG.info("Room is archived. Set as archived in database and remove from known users")
                    self.database.archiveRoom(room=room)
                    self.communication.knownUserData.removeKnownUser(botName=telegramBotName,
                                                                     telegramID=room.roomTelegramID)
        except Exception as e:
            LOG_aeaa.exception("Error in removeBotFromGroupAfterElection: " + str(e))
            AfterElectionAdditionalActionsException("Error in "
                "AfterElectionAdditionalActions.removeBotFromGroupAfterElection: " + str(e))

    def removeBotFromCDgroup(self,
                             executionTime: datetime,
                             previousElection: Election,
                             deadlineInMinutes: int,
                             electCurr: ElectCurrTable,
                             telegramBotName: str,
                             telegramUserBotName: str):
        assert isinstance(executionTime, datetime), "executionTime is not a datetime object"
        assert isinstance(previousElection, Election), "currentElection is not an Election object"
        assert isinstance(deadlineInMinutes, int), "deadlineInMinutes is not an integer"
        assert isinstance(electCurr, ElectCurrTable), "electCurr is not an ElectCurrTable object"
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        try:
            LOG_aeaa.debug("In removeBotFromCDgroup")
            if self.isInTimeframe(executionTime=executionTime,
                                 electionDate=electCurr.getLastElectionTime(),
                                 deadlineInMinutes=deadlineInMinutes,
                                 executionTimeframeInMinutes=60) is False:

                LOG_aeaa.debug("It is not time to remove bot from groups. Do not do anything")
                return

            LOG.info("... is between time span for notification. Send it if not sent yet")
            # get all rooms from database for previous election
            rooms: list[Room] = self.getCDroomFromDatabase(election=previousElection,
                                                          predisposedBy=telegramUserBotName)
            for room in rooms:
                LOG.info("Removing bot from room: " + str(room.roomID))
                if room.isArchived is True:
                    LOG.info("Room is already archived. Do not do anything")
                    continue
                LOG.info("Removing bot from room: " + str(room.roomID))
                userLeft: bool = self.leavingTheRoom(sessionType=SessionType.USER, room=room)
                botLeft: bool = self.leavingTheRoom(sessionType=SessionType.BOT, room=room)

                LOG.debug("userLeft: " + str(userLeft) + " botLeft: " + str(botLeft))
                if botLeft is True:
                    # when bot left the room, the room should be archived
                    LOG.info("Set as archived in database and remove from known users")
                    self.database.archiveRoom(room=room)
                    self.communication.knownUserData.removeKnownUser(botName=telegramBotName,
                                                                     telegramID=room.roomTelegramID)

        except Exception as e:
            LOG_aeaa.exception("Error in removeBotFromCDgroup: " + str(e))
            AfterElectionAdditionalActionsException("Error in "
                "AfterElectionAdditionalActions.removeBotFromCDgroup: " + str(e))

    def do(self, election: Election, telegramUserBotName: str, telegramBotName: str, electCurr: ElectCurrTable):
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(electCurr, ElectCurrTable), "electCurr is not an ElectCurrTable object"
        try:
            LOG_aeaa.debug("In AfterElectionAdditionalActions.do")

            if electCurr is None:
                LOG.error("electCurr is None. Something went wrong when getting/parsing elect.Curr table.")
                return
            if electCurr.getLastElectionTime() is None or \
                    isinstance(electCurr.getLastElectionTime(), datetime) is False:
                LOG_aeaa.error("electCurr.getLastElectionTime() is not datetime. Something went wrong when getting/parsing "
                          "elect.Curr table. Do not do anything")
                return

            # get last election if exists in database
            previousElection: Election = self.database.getElectionByDate(contract=election.contract,
                                                                         date=electCurr.getLastElectionTime())

            if previousElection is None:
                LOG_aeaa.error("previousElection is not found in the database. Do not do anything")
                return

            # remove bot from all groups 15 days after election
            self.removeBotFromGroupAfterElectionAfterDefinedMinutes(
                                                 executionTime=self.executionTime,
                                                 electCurr=electCurr, # from contract
                                                 previousElection=previousElection,
                                                 deadlineInMinutes=15 * 24 * 60, # 15 days * 24 hours * 60 minutes
                                                 telegramBotName=telegramBotName,
                                                 telegramUserBotName=telegramUserBotName)

            # remove bot and user bot from CD group 1 day after election
            self.removeBotFromCDgroup(executionTime=self.executionTime,
                                      electCurr=electCurr,  # from contract
                                      previousElection=previousElection,
                                      deadlineInMinutes= 24 * 60,  # 1 day = 24 hours * 60 minutes
                                      telegramBotName=telegramBotName,
                                      telegramUserBotName=telegramUserBotName)

        except Exception as e:
            LOG_aeaa.exception("Error in AfterEveryRoundAdditionalActions.do: " + str(e))

    def removeBotFromAllGroups(self):
        LOG_aeaa.debug("removeBotFromAllGroups started")
        for group in self.edenData.groups:
            try:
                asyncio.get_event_loop().run_until_complete(self.communication.leaveChat(
                    sessionType=SessionType.BOT,
                    chatId=group.id))
            except pyrogram.errors.exceptions.bad_request_400.ChatAdminRequired:
                LOG_aeaa.debug("removeBotFromAllGroups: ChatAdminRequired")
                pass
            except pyrogram.errors.exceptions.bad_request_400.ChatNotModified:
                LOG_aeaa.debug("removeBotFromAllGroups: ChatNotModified")
                pass
            except pyrogram.errors.exceptions.bad_request_400.ChatWriteForbidden:
                LOG_aeaa.debug("removeBotFromAllGroups: ChatWriteForbidden")
                pass
            except pyrogram.errors.exceptions.bad_request_400.PeerIdInvalid:
                LOG_aeaa.debug("removeBotFromAllGroups: PeerIdInvalid")
                pass
            except pyrogram.errors.exceptions.bad_request_400.PeerIdNotSupported:
                LOG_aeaa.debug("removeBotFromAllGroups: PeerIdNotSupported")
                pass
            except pyrogram.errors.exceptions.bad_request_400.UserIsBlocked:
                LOG_aeaa.debug("removeBotFromAllGroups: UserIsBlocked")
                pass
            except pyrogram.errors.exceptions.bad_request_400.UserNotParticipant:
                LOG_aeaa.debug("removeBotFromAllGroups: UserNotParticipant")
                pass
            except pyrogram.errors.exceptions.bad_request_400.UserNotMutualContact:
                LOG_aeaa.debug("removeBotFromAllGroups: User")



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
        LOG_aeraa.debug("AfterEveryRoundAdditionalActions object created")

    def isVideoCallRunning(self, chatId: Union[int, str]):
        assert isinstance(chatId, (int, str)), "chatId is not an integer or string"
        try:
            isRunning = asyncio.get_event_loop().run_until_complete(self.communication.isVideoCallRunning(
                                                                        sessionType=SessionType.BOT,
                                                                        chatId=chatId))

            LOG_aeraa.debug("Is video call running: " + str(isRunning) + " in chat " + str(chatId))
            if isRunning is None:
                LOG_aeraa.error("Error while getting information if video call is active. Return False")
                return False
            return isRunning
        except Exception as e:
            LOG_aeraa.exception("Error while getting information if video call is active: " + str(e))
            return False

    def isInChat(self, chatId: Union[int, str]):
        assert isinstance(chatId, (int, str)), "chatId is not an integer or string"
        try:
            isInChat = self.communication.isInChat(sessionType=SessionType.BOT, chatId=chatId)

            LOG_aeraa.debug("Is user(bot): " + str(isInChat) + " in chat " + str(chatId))
            if isInChat is None:
                LOG_aeraa.error("AdditionalActions.isInCat; Value is None.")
                raise AfterEveryRoundAdditionalActionsException("AdditionalActions.isInCat; Value is None.")
            return isInChat
        except Exception as e:
            LOG_aeraa.exception("Error while getting information if user(bot) is in chat: " + str(e))
            return None

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

            result: bool = self.communication.sendPhoto(sessionType=SessionType.BOT,
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
                            text=button[0]['text'],
                            url=button[0]['value']
                        )
                    ]
                ]
            )
            result: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                          chatId=room.roomTelegramID,
                                                          text=text,
                                                          inlineReplyMarkup=replyMarkup)
            LOG_aeraa.debug("Last message to group sent to room " + str(room.roomID) + ". Result: " + str(result))
        except Exception as e:
            LOG_aeraa.exception("Error while sending message to room " + str(room.roomID) + ": " + str(e))

    def removingBotFromGroupsAndDeleteUnusedGroups(self, round: int,  telegramBotName: str, telegramUserBotName: str):
        assert isinstance(round, int), "round is not an integer"
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        try:
            LOG_aeraa.debug("Removing the bot from groups")
            rooms: list[Room] = self.getGroupsInRound(round=round, predisposedBy=telegramUserBotName)

            telegramBotNameCp = REMOVE_AT_SIGN_IF_EXISTS(telegramBotName.lower())
            telegramUserBotNameCp = REMOVE_AT_SIGN_IF_EXISTS(telegramUserBotName.lower())

            if rooms is None or len(rooms) == 0:
                LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                " No rooms found")
                return

            for room in rooms:
                try:

                    # we want to get actual members in the group, not the ones in the database
                    members: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.BOT,
                                                                                       chatId=room.roomTelegramID)
                    if len(members) == 0:
                        LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                       " Requested as bot. No members found in the group " + str(room.roomTelegramID))

                        members: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.USER,
                                                                                           chatId=room.roomTelegramID)
                        if len(members) == 0:
                            LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                           " Requested as user. No members found in the group " + str(room.roomTelegramID))
                    counterUsers = 0
                    userBotInGroup: bool = False
                    botInGroup: bool = False
                    for member in members:
                        try:
                            member.username = REMOVE_AT_SIGN_IF_EXISTS(member.username.lower())
                        except Exception as e:
                            LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                            "Cannot update username: " + str(member.username))


                        # bots are not counted
                        if member.username == telegramBotNameCp:
                            botInGroup = True
                            continue
                        # user bot is not counted
                        if member.username == telegramUserBotNameCp:
                            userBotInGroup = True
                            continue
                        if member.isBot:
                            continue
                        counterUsers += 1

                    # if no users are found in the group, the group will be deleted!
                    if counterUsers == 0:
                        LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: "
                                      "No users found in the group " + str(room.roomTelegramID) + ". Removing the group")
                        response: bool = self.communication.deleteGroup(chatId=room.roomTelegramID)
                        if response:
                            self.database.archiveRoom(room=room)
                        LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                        " archiveRoom with id " + str(room.roomTelegramID + " done"))
                    else:
                        if botInGroup:
                            LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: "
                                          "Removing the bot from the group " + str(room.roomTelegramID))
                            #TODO: bot should be removed from group after 2 weeks, because of the invite link - do it after election
                            #response: bool = self.communication.leaveChat(sessionType=SessionType.BOT,
                            #                                              chatId=room.roomTelegramID)
                            #LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                            #            "Is bot left chat with id " + str(room.roomTelegramID + " done? " + str(response)))
                        if userBotInGroup:
                            response: bool = self.communication.leaveChat(sessionType=SessionType.USER,
                                                                          chatId=room.roomTelegramID)
                            LOG_aeraa.debug("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                                            "Is USER-bot left chat with id " + str(room.roomTelegramID + " done? " + str(response)))
                            if response is False:
                                LOG_aeraa.error("Error while removing USER_BOT(" + telegramUserBotName + ") from the group "
                                                + str(room.roomTelegramID))
                except Exception as e:
                    LOG_aeraa.error("AfterEveryRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups.inner "
                                    "exp: Error while removing the bot from the group or deleting unused groups"
                                    + str(room.roomTelegramID) + ": " + str(e))

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
                LOG.info("Checking room: " + str(room.roomID) + ", tgID:" + str(room.roomTelegramID))
                if self.isInChat(chatId=room.roomTelegramID) is not True:
                    LOG.debug("Bot is not in group " + str(room.roomTelegramID) + ". Skipping")
                    continue

                if self.isVideoCallRunning(chatId=room.roomTelegramID):
                    LOG.debug("Video call is running in group " + str(room.roomTelegramID) + ". Stopping it")
                    self.videoCallStillRunningSendMsg(room=room)
                else:
                    self.roundEndMsg(room=room)
                    LOG.debug("Video call is not running in group " + str(room.roomTelegramID))
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

    def doAfterSomeTimeRunsOut(self):
        #TODO: implement actions after some time runs out, to send message about running video call after 10 minutes
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
        LOG_fraa.debug("FinalRoundAdditionalActions object created")

    def do(self, telegramBotName: str, telegramUserBotName: str):
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        try:
            self.deleteUnusedGroups(telegramBotName=telegramBotName,
                                    telegramUserBotName=telegramUserBotName)
        except Exception as e:
            LOG_fraa.exception("Error in FinalRoundAdditionalActions.do: " + str(e))

    def deleteUnusedGroups(self, telegramBotName: str, telegramUserBotName: str):
        assert isinstance(telegramBotName, str), "telegramBotName is not a string"
        assert isinstance(telegramUserBotName, str), "telegramUserBotName is not a string"
        try:
            LOG_fraa.debug("Removing the bot from groups")
            dummyElectionForFreeRooms: Election = self.database.getDummyElection(election=self.election)
            if dummyElectionForFreeRooms is None:
                raise FinalRoundAdditionalActionsException("No dummy election set in database")

            #  remove unused rooms
            rooms: list[Room] = self.database.getRoomsPreelection(election=dummyElectionForFreeRooms,
                                                                  predisposedBy=telegramUserBotName)

            if rooms is None or len(rooms) == 0:
                LOG_fraa.error("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups: No rooms found")
                return

            for room in rooms:
                LOG_fraa.debug("FinalRoundAdditionalActions.deleteUnusedGroups: "
                               "Removing the group: " + str(room.roomTelegramID))
                chatIdInt: int = None
                try:
                    if isinstance(room.roomTelegramID, str):
                        chatIdInt = int(room.roomTelegramID)
                    elif isinstance(room.roomTelegramID, int):
                        chatIdInt = room.roomTelegramID
                    else:
                        raise Exception("ChatId is not str or int")
                except Exception as e:
                    LOG.exception("Not int value stored in string: " + str(e))
                    return None

                self.communication.deleteGroup(chatId=chatIdInt)
                self.database.archiveRoom(room=room)
                LOG_fraa.debug("FinalRoundAdditionalActions.removingBotFromGroupsAndDeleteUnusedGroups:"
                               " archiveRoom with id " + str(chatIdInt) + " done")

        except Exception as e:
            raise FinalRoundAdditionalActionsException("Error while removing the bot from groups: " + str(e))


#
# This class is used to manage the additional actions of the bot.
#

class AdditionalActionManagement:
    def __init__(self, additionalActions):
        self.additionalActions = additionalActions
