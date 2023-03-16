from chain import EdenData
from database import Database, Election, ExtendedRoom
from database.room import Room
from debugMode.modeDemo import Mode
from log import Log
from transmission import Communication, SessionType
from transmission.Communication import CustomMember


# This class is used to do additional actions at the end of the elections like:
# - Cleaning unused groups/channels
# - Removing the bot and user bot from used the groups/channels


class FinalRoundAdditionalActionsException(Exception):
    pass

class AdditionalActionManagementException(Exception):
    pass


LOG_fraa = Log(className="FinalRoundAdditionalActions")
LOG = Log(className="AdditionalActionManagement")


class FinalRoundAdditionalActions:
    def __init__(self, election: Election, edenData: EdenData, database: Database, communication: Communication, mode: Mode):
        assert isinstance(election, Election), "election is not an Election object"
        assert isinstance(edenData, EdenData), "edenData is not an EdenData object"
        assert isinstance(database, Database), "database is not a Database object"
        assert isinstance(communication, Communication), "communication is not a Communication object"
        assert isinstance(mode, Mode), "mode is not a Mode object"
        self.election = election
        self.edenData = edenData
        self.database = database
        self.communication = communication
        self.mode = mode
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
                        #bots are not counted
                        if member.isBot:
                            continue
                        #user bot is not counted
                        if member.username == telegramUserBotName:
                            continue
                        if member.username == telegramBotName:
                            #probably never happens, because of .isBot check before
                            continue
                        counterUsers += 1

                    #if no users are found in the group, the group is deleted, only LAST GROUP is not deleted, just
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
                                       "Is USER bot leaving chat with id " + str(room.chatId + " done? " + str(response)))
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


