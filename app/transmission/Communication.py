import asyncio
import os
import threading
from datetime import datetime, timedelta
from enum import Enum

from pyrogram.errors import FloodWait, PeerIdInvalid
from pyrogram.filters import new_chat_members
from pyrogram.handlers import MessageHandler
from pyrogram.methods.decorators import on_chat_member_updated
from pyrogram.types import Chat, InlineKeyboardMarkup, ChatPrivileges, InlineKeyboardButton, BotCommand

from app.constants.parameters import *
from app.database import Database
from app.database.participant import Participant
from app.dateTimeManagement import DateTimeManagement
from app.knownUserManagement import KnownUserData
from app.log.log import Log

from multiprocessing import Process

from pyrogram import Client, emoji, filters, types, idle

import time

from app.text.textManagement import GroupCommunicationTextManagement, Button, BotCommunicationManagement, \
    WellcomeMessageTextManagement


# api_id = 48490
# api_hash = "507315c8796f15903299b47730838c77"

# , /*bot_token="5512475717:AAGp0a451eha7X00wVJ4csCC0Mh_U1J1nxk"
# async def main():
#    async with Client("bot1", api_id, api_hash) as app:
#        await app.send_message("me", "Greetings from **Pyrogram**!")

class SessionType(Enum):
    USER = 1
    BOT = 2
    BOT_THREAD = 3


class CommunicationException(Exception):
    pass


LOG = Log(className="Communication")

DATABASE_CONST = None
class Communication(): #threading.Thread
    # sessions = {}
    sessionUser: Client = None
    sessionBot: Client = None
    sessionBotThread: Client = None
    isInitialized: bool = False
    pyrogram: Process = None

    def __init__(self, database: Database):
        assert isinstance(database, Database), "Database should be Database"
        LOG.info("Init communication")
        self.database = database
        global DATABASE_CONST
        DATABASE_CONST = database
        self.knownUserData: KnownUserData = KnownUserData(database=database)
        #threading.Thread.__init__(self, daemon=True)

    #def run(self):
    #    self.idle()

    def startComm(self, apiId: int, apiHash: str, botToken: str):
        assert isinstance(apiId, int), "ApiId should be int"
        assert isinstance(apiHash, str), "ApiHash should be str"
        assert isinstance(botToken, str), "BotToken should be str"
        LOG.debug("Starting communication sessions..")
        try:
            #self.startCommAsyncSession(apiId=apiId, apiHash=apiHash, botToken=botToken)

            LOG.debug("... user session")
            self.setSession(sessionType=SessionType.USER,
                            client=Client(name=communication_session_name_user,
                                          api_id=apiId,
                                          api_hash=apiHash))
            self.startSession(sessionType=SessionType.USER)



            LOG.debug("... bot session")
            self.setSession(sessionType=SessionType.BOT,
                            client=Client(name=communication_session_name_bot,
                                          api_id=apiId,
                                          api_hash=apiHash,
                                          bot_token=botToken))

            # client: Client = self.getSession(SessionType.BOT)
            """self.sessionBot.add_handler(
                MessageHandler(callback=Communication.wellcomeProcedure, filters=filters.new_chat_members))

            self.sessionBot.add_handler(
                MessageHandler(callback=Communication.commandResponseStart,
                               filters=filters.command(commands=["start"]) & filters.private)
            )

            self.sessionBot.add_handler(
                MessageHandler(callback=Communication.commandResponseInfo,
                               filters=filters.command(commands=["info"]) & filters.private)
            )"""


            self.startSession(sessionType=SessionType.BOT)


            self.sessionBot.set_bot_commands([
                BotCommand("start", "Register with the bot"),
                BotCommand("status", "Check if the Up Vote Bot is running"),
                BotCommand("donate", "Support the development of Up Vote Bot features"),
                BotCommand("admin", "Promote yourself to admin in groups created by Up Vote Bot")])

            self.isInitialized = True
            LOG.debug("... done!")
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise CommunicationException("Exception: " + str(e))

    def startCommAsyncSession(self, apiId: int, apiHash: str, botToken: str):
        LOG.info("Start async bot session - event driven actions")
        #self.startSession(sessionType=SessionType.BOT_THREAD)
        self.pyrogram = Process(target=self.startSessionAsync, args=(apiId, apiHash, botToken))
        self.pyrogram.start()
        self.pyrogram.pid
        #asyncio.run(self.startSessionAsync(apiId=apiId, apiHash=apiHash, botToken=botToken))
        #task1 = asyncio.run(self.startSessionAsync(apiId=apiId, apiHash=apiHash, botToken=botToken))
        kva = 8

    def startSessionAsync(self, apiId: int, apiHash: str, botToken: str):
        self.setSession(sessionType=SessionType.BOT_THREAD,
                        client=Client(name=communication_session_name_async_bot + "1",
                                      api_id=apiId,
                                      api_hash=apiHash,
                                      bot_token=botToken))

        self.sessionBotThread.add_handler(
            MessageHandler(callback=self.wellcomeProcedure,
                           filters=on_chat_member_updated), group=-1
        )

        self.sessionBotThread.add_handler(
            MessageHandler(callback=self.commandResponseStart,
                           filters=filters.command(commands=["start"]) & filters.private), group=4
        )

        self.sessionBotThread.add_handler(
            MessageHandler(callback=self.commandResponseStatus,
                           filters=filters.command(commands=["status"]) & filters.private), group=3
        )

        self.sessionBotThread.add_handler(
            MessageHandler(callback=self.commandResponseDonate,
                           filters=filters.command(commands=["donate"]) & filters.private), group=2
        )

        self.sessionBotThread.add_handler(
            MessageHandler(callback=self.commandResponseAdmin,
                           filters=filters.command(commands=["admin"])), group=1
        )

        #self.startSession(sessionType=SessionType.BOT_THREAD)
        self.sessionBotThread.start()
        #self.sessionBotThread.
        idle()

        #idle()

    def addKnownUserAndUpdateLocal(self, botName: str, chatID: int):
        assert isinstance(botName, str), "BotName should be str"
        assert isinstance(chatID, (int,str)), "chatID should be int or str"
        LOG.info("Adding known user: " + str(chatID) + " for bot: " + botName)
        self.knownUserData.setKnownUser(botName=botName, telegramID=chatID, isKnown=True)
        self.updateKnownUserData(botName=botName)
    def updateKnownUserData(self, botName: str) -> bool:
        assert isinstance(botName, str), "BotName should be str"
        try:
            LOG.info("Updating known user data for bot: " + botName)
            return self.knownUserData.getKnownUsersOptimizedSave(botName=botName)
        except Exception as e:
            LOG.exception("Communication.updateKnownUserData exception: " + str(e))

    def isInitialized(self) -> bool:
        return self.isInitialized

    def getSession(self, sessionType: SessionType) -> Client:
        LOG.info("Get session: " + str(sessionType))
        return self.sessionBot if sessionType == SessionType.BOT else self.sessionUser

    def setSession(self, sessionType: SessionType, client: Client):
        LOG.info("Set session: " + str(sessionType))
        if sessionType == SessionType.BOT:
            self.sessionBot = client
        elif sessionType == SessionType.BOT_THREAD:
            self.sessionBotThread = client
        else:
            self.sessionUser = client

    def startSession(self, sessionType: SessionType):
        LOG.info("Start session: " + str(sessionType))
        if sessionType == SessionType.BOT:
            self.sessionBot.start()
        elif sessionType == SessionType.BOT_THREAD:
            self.sessionBotThread.start()
        else:
            self.sessionUser.start()

    def sendPhoto(self,
                  sessionType: SessionType,
                  chatId: (str, int),
                  photoPath: str,
                  caption: str = None,
                  replyMarkup: InlineKeyboardMarkup = None):
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(photoPath, str), " photoPath should be str"
            assert isinstance(caption, (str, type(None))), "Caption should be str or None"
            LOG.info("Sending photo to: " + str(chatId))

            if isinstance(chatId, type(None)) or \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return False

            if sessionType == SessionType.BOT:
                self.sessionBot.send_photo(chat_id=chatId,
                                           photo=open(photoPath, 'rb'),
                                           caption=caption,
                                           reply_markup=replyMarkup)
            else:
                self.sessionUser.send_photo(chat_id=chatId,
                                            photo=open(photoPath, 'rb'),
                                            caption=caption,
                                            reply_markup=replyMarkup)
            return True
        except Exception as e:
            LOG.exception("Exception (in sendPhoto): " + str(e))

        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False

    def sendMessage(self,
                    sessionType: SessionType,
                    chatId: (str, int),
                    text: str,
                    disableWebPagePreview=False,
                    scheduleDate: datetime = None,
                    inlineReplyMarkup: InlineKeyboardMarkup = None,
                    ) -> bool:
        # warning:
        # when sessionType is SessionType.USER you cannot send message with inline keyboard
        LOG.info("Send message to: " + str(chatId) + " with text: " + text
                 + " and scheduleDate: " + str(scheduleDate) if scheduleDate is not None else "<now>")
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert (sessionType is SessionType.BOT) or \
                   (sessionType is SessionType.USER and inlineReplyMarkup is None), \
                "when SessionType is USER there is no option to send inlineReplyMarkup!"

            if sessionType == SessionType.BOT:
                if isinstance(chatId, type(None)) or \
                        self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                             telegramID=str(chatId)) is False:
                    LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                    return False

                response = self.sessionBot.send_message(chat_id=chatId,
                                                        text=text,
                                                        schedule_date=scheduleDate,
                                                        reply_markup=inlineReplyMarkup,
                                                        disable_web_page_preview=disableWebPagePreview)
            else:
                response = self.sessionUser.send_message(chat_id=chatId,
                                                         text=text,
                                                         schedule_date=scheduleDate,
                                                         reply_markup=inlineReplyMarkup,
                                                         disable_web_page_preview=disableWebPagePreview)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendMessage) Waiting time (in seconds): " + str(e.value))
            time.sleep(e.value)
            return self.sendMessage(sessionType=sessionType, chatId=chatId, text=text, replyMarkup=inlineReplyMarkup)
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            return False

    def sendLogToAdmin(self, level: str, log: str):
        LOG.info("Sending log (level: " + level + ") to admin: " + log)
        if telegram_admins_id is not None:
            for adminId in telegram_admins_id:
                self.sendMessage(sessionType=SessionType.BOT, chatId=adminId, text=log)

    def createGroup(self, name: str, participants: list) -> int:
        LOG.info("Creating group: " + name + " with participants: " + str(participants))
        try:
            assert name is not None, "Name should not be null"
            assert participants is not None, "Participants should not be null"
            chat: Chat = self.sessionUser.create_group(title=name,
                                                       users=participants)

            return chat.id
        except Exception as e:
            LOG.exception("Exception (in createGroup): " + str(e))
            return None

    def createSuperGroup(self, name: str, description: str) -> int:
        LOG.info("Creating super group: " + name + " with description: " + description)
        try:
            assert name is not None, "Name should not be null"
            assert description is not None, "Description should not be null"
            chat: Chat = self.sessionUser.create_supergroup(title=name,
                                                            description=description)
            return chat.id
        except Exception as e:
            LOG.exception("Exception (in createSuperGroup): " + str(e))
            return None

    def userExists(self, userID: str) -> list:
        assert userID is not None, "userID should not be null"
        try:
            # not in use
            kva1 = self.sessionBot.resolve_peer(peer_id=userID)
            return True
        except Exception as e:
            LOG.exception("Exception (in getUsers): " + str(e))
            return False

        # return self.sessionUser.iter_participants(self.sessionUser.get_me())

    def getInvitationLink(self, sessionType: SessionType, chatId: (str, int)) -> str:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        LOG.debug("Getting invitation link for chat: " + str(chatId) + " Make sure that user/bot is admin and keep in"
                                                                       "mind that link is valid until next call of this"
                                                                       "method. Previous link will be revoked.")
        LOG.info("Get invitation link for chat: " + str(chatId))
        try:
            if isinstance(chatId, type(None)) or \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return None

            inviteLink: str = self.sessionUser.export_chat_invite_link(chat_id=chatId) \
                if sessionType == SessionType.USER \
                else \
                self.sessionBot.export_chat_invite_link(chat_id=chatId)
            LOG.debug("Invite link: " + inviteLink)
            return inviteLink
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return None
        except Exception as e:
            LOG.exception("Exception (in getInvitationLink): " + str(e))
            return None

    def archiveGroup(self, chatId: (str, int)) -> bool:
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        LOG.info("Archiving group: " + str(chatId))
        try:
            if isinstance(chatId, type(None)) or \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return True

            self.sessionUser.archive_chat(chat_id=chatId)
            return True
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except Exception as e:
            LOG.exception("Exception (in archiveGroup): " + str(e))
            return False

    def callbackQuery(self, callbackQuery: types.CallbackQuery):
        LOG.info("Callback query: " + str(callbackQuery))
        try:
            # TODO: function in progress
            assert callbackQuery is not None, "CallbackQuery should not be null"
            # self.sessionBot.answer_callback_query(callback_query_id=callbackQuery.id)

            # self.sessionBot.on_callback_query(filters=filters.)

        except Exception as e:
            LOG.exception("Exception (in callbackQuery): " + str(e))

    def deleteGroup(self, chatId: (str, int)) -> bool:
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        LOG.info("Deleting group: " + str(chatId))
        try:
            if isinstance(chatId, type(None)) or \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return False

            self.sessionUser.delete_chat(chat_id=chatId)
            return True
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except Exception as e:
            LOG.exception("Exception (in deleteGroup): " + str(e))
            return False

    def addChatMembers(self, chatId: (str, int), participants: list) -> bool:
        LOG.info("Adding participants to group: " + str(chatId) + " with participants: " + str(participants))
        try:
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert participants is not None, "Participants should not be null"

            knownParticipants = []
            for participant in participants:
                if isinstance(participant, type(None)) == False and \
                        self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                             telegramID=str(chatId)):
                    knownParticipants.append(participant)

            self.sessionUser.add_chat_members(chat_id=chatId,
                                              user_ids=knownParticipants)
            return True
        except Exception as e:
            LOG.exception("Exception (in addChatMembers): " + str(e))
            return False

    def promoteMembers(self, sessionType: SessionType, chatId: (str, int), participants: list) -> bool:
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(participants, list), "Participants should be list"
            LOG.info("Promoting participants to group: " + str(chatId) + " with participants: " + str(participants))

            if sessionType == SessionType.BOT:
                if isinstance(chatId, type(None)) or \
                        self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                             telegramID=str(chatId)) is False:
                    LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                    return False

            for participant in participants:
                try:
                    if sessionType == SessionType.USER:
                        self.sessionUser.promote_chat_member(chat_id=chatId,
                                                             user_id=participant,
                                                             privileges=ChatPrivileges(
                                                                 can_manage_chat=True,
                                                                 can_delete_messages=True,
                                                                 can_manage_video_chats=True,
                                                                 can_restrict_members=True,
                                                                 can_promote_members=True,
                                                                 can_change_info=True,
                                                                 can_invite_users=True,
                                                                 can_pin_messages=True,
                                                                 is_anonymous=False
                                                             )
                                                             )

                    else:
                        if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                                telegramID=str(participant)):
                            self.sessionBot.promote_chat_member(chat_id=chatId,
                                                                user_id=participant,
                                                                privileges=ChatPrivileges(
                                                                    can_manage_chat=True,
                                                                    can_delete_messages=True,
                                                                    can_manage_video_chats=True,
                                                                    can_restrict_members=True,
                                                                    can_promote_members=True,
                                                                    can_change_info=True,
                                                                    can_invite_users=True,
                                                                    can_pin_messages=True,
                                                                    is_anonymous=False
                                                                )
                                                                )
                except Exception as e:
                    LOG.exception("Exception (in promoteMembers): " + str(e))
            return True
        except Exception as e:
            LOG.exception("Exception (in promoteMembers): " + str(e))
            return False

    def setChatDescription(self, chatId: (str, int), description: str) -> bool:
        LOG.info("Setting description to group: " + str(chatId) + " with description: " + str(description))
        try:
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert description is not None, "Description should not be null"
            self.sessionUser.set_chat_description(chat_id=chatId,
                                                  description=description)
            return True
        except Exception as e:
            LOG.exception("Exception (in setChatDescription): " + str(e))
            return False

    def leaveChat(self, sessionType: SessionType, chatId: (str, int)) -> bool:
        assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"

        LOG.info("Leaving group: " + str(chatId))
        LOG.info("SessionType: " + str(sessionType))
        try:
            if sessionType == SessionType.USER:
                self.sessionUser.leave_chat(chat_id=chatId)
            else:
                if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                        telegramID=str(chatId)) == False:
                    LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                    return False
                self.sessionBot.leave_chat(chat_id=chatId)
            return True
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except Exception as e:
            LOG.exception("Exception (in leaveChat): " + str(e))
            return False

    #
    # Filters management
    #

    async def wellcomeProcedure(self, client: Client, message):

        if message.new_chat_members is None or len(message.new_chat_members) == 0 or message.chat.type.name != "SUPERGROUP":
            return
        target = message.new_chat_members[0]

        LOG.success("New chat member: " + str(message.new_chat_members))
        chatid = message.chat.id
        newMember = target

        if isinstance(newMember, types.User):
            LOG.success("Wellcome message to user: " + str(newMember.id))
            if newMember.is_bot:
                LOG.debug("...is bot. Do nothing")
                return
            result = await client.promote_chat_member(chat_id=chatid,
                                                      user_id=newMember.username,
                                                      privileges=ChatPrivileges(
                                                          can_manage_chat=True,
                                                          can_delete_messages=True,
                                                          can_manage_video_chats=True,
                                                          can_restrict_members=True,
                                                          can_promote_members=True,
                                                          can_change_info=True,
                                                          can_invite_users=True,
                                                          can_pin_messages=True,
                                                          is_anonymous=False
                                                      ))
            LOG.success("Response (promote_chat_member): " + str(result))
            wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()

            result1 = await client.send_message(chat_id=chatid,
                                                text=wellcomeMessageObject.getWellcomeMessage(
                                                    participantAccountName=str(newMember.username)
                                                ))

            LOG.success("Response (send_message): " + str(result1))


    async def wellcomeProcedureOld(client: Client, message):
        try:
            LOG.success("New chat member: " + str(message.new_chat_members))
            chatid = message.chat.id

            ##############################
            for newMember in message.new_chat_members:
                if isinstance(newMember, types.User):
                    LOG.success("Wellcome message to user: " + str(newMember.id))
                    LOG.debug(
                        "... with username: " + str(newMember.username) if newMember.username is not None else "None")
                    LOG.debug("...name: " + str(newMember.first_name) if newMember.first_name is not None else "None")
                    LOG.debug(
                        "...last name: " + str(newMember.last_name) if newMember.last_name is not None else "None")

                    # if new member is a bot do nothing
                    if newMember.is_bot:
                        LOG.debug("...is bot. Do nothing")
                        continue
                    result = await client.promote_chat_member(chat_id=chatid,
                                                              user_id=newMember.username,
                                                              privileges=ChatPrivileges(
                                                                  can_manage_chat=True,
                                                                  can_delete_messages=True,
                                                                  can_manage_video_chats=True,
                                                                  can_restrict_members=True,
                                                                  can_promote_members=True,
                                                                  can_change_info=True,
                                                                  can_invite_users=True,
                                                                  can_pin_messages=True,
                                                                  is_anonymous=False
                                                              ))
                    LOG.success("Response (promote_chat_member): " + str(result))
                    wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()

                    result1 = await client.send_message(chat_id=chatid,
                                            text=wellcomeMessageObject.getWellcomeMessage(
                                                participantAccountName=str(newMember.username)
                                            ))

                    LOG.success("Response (send_message): " + str(result1))

            ####################
            return


            LOG.success(".. in chat: " + str(chatid))
            #database: Database = Database()
            database: Database = DATABASE_CONST
            for newMember in message.new_chat_members:
                if isinstance(newMember, types.User):
                    LOG.success("Wellcome message to user: " + str(newMember.id))
                    LOG.debug(
                        "... with username: " + str(newMember.username) if newMember.username is not None else "None")
                    LOG.debug("...name: " + str(newMember.first_name) if newMember.first_name is not None else "None")
                    LOG.debug(
                        "...last name: " + str(newMember.last_name) if newMember.last_name is not None else "None")

                    # if new member is a bot do nothing
                    if newMember.is_bot:
                        LOG.debug("...is bot. Do nothing")
                        continue



                    # promote only users who supposed to be in this room
                    participants: list[Participant] = database.getUsersInRoom(roomTelegramID=str(chatid))
                    #participants: list[Participant] = [Participant(telegramID="123456789", username="testuser")]
                    if participants is None:
                        LOG.error("WellcomeProcedure; No participants in this room or room not found")
                        return
                    for participant in participants:
                        if participant.telegramID is None:
                            LOG.error("WellcomeProcedure; Participant telegramID is None")
                            continue

                        if participant.telegramID[0] == "@":
                            participant.telegramID = participant.telegramID[1:]

                        if newMember.username[0] == "@":
                            newMember.username = newMember.username[1:]

                        if participant.telegramID.lower() == newMember.username.lower():
                            LOG.debug(
                                "User supposed to be in this room: " + str(participant.telegramID) + " - promoting!")


                            result = await client.promote_chat_member(chat_id=chatid,
                                                             user_id=newMember.username,
                                                             privileges=ChatPrivileges(
                                                                 can_manage_chat=True,
                                                                 can_delete_messages=True,
                                                                 can_manage_video_chats=True,
                                                                 can_restrict_members=True,
                                                                 can_promote_members=True,
                                                                 can_change_info=True,
                                                                 can_invite_users=True,
                                                                 can_pin_messages=True,
                                                                 is_anonymous=False
                                                             ))
                            LOG.success("Response (promote_chat_member): " + str(result))
                            wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()

                            result1 = await client.send_message(chat_id=chatid,
                                                      text=wellcomeMessageObject.getWellcomeMessage(
                                                          participantAccountName=str(participant.accountName)
                                                      ))

                            LOG.success("Response (send_message): " + str(result1))


                            LOG.success(
                                "Promoting  user " + str(participant.telegramID) + " to admin successfully done!")
                            break
                else:
                    LOG.success("New member is not instance of 'User'")
        except Exception as e:
            LOG.exception("Exception (in wellcomeProcedure): " + str(e))
            return

    async def commandResponseStart(self, client: Client, message):
        try:
            LOG.success("Response on command 'start' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            database: Database = DATABASE_CONST
            if isinstance(message.chat.username, str):
                LOG.debug("Username exists: " + str(message.chat.username))

            participant: Participant = database.getParticipantByTelegramID(telegramID=message.chat.username)

            # reply_markup=inlineReplyMarkup, disable_web_page_preview=disableWebPagePreview

            #add user to known users
            knownUserData: KnownUserData = KnownUserData(database=database)
            knownUserData.setKnownUser(botName=telegram_bot_name, telegramID=message.chat.username, isKnown=True)

            botCommunicationManagement: BotCommunicationManagement = BotCommunicationManagement()
            telegramID: str = "@" + str(message.chat.username) if message.chat.username is not None else None
            if participant is None:
                LOG.error("Participant not found in database")
                await client.send_message(chat_id=chatid,
                                          text=botCommunicationManagement.startCommandNotKnownTelegramID(
                                              telegramID=telegramID),
                                          reply_markup=InlineKeyboardMarkup(
                                              inline_keyboard=
                                              [
                                                  [
                                                      InlineKeyboardButton(
                                                          text=botCommunicationManagement.startCommandNotKnownTelegramIDButtonText(),
                                                          url=eden_support_url),

                                                  ]
                                              ]
                                          )
                                          )

            else:
                LOG.debug("Participant found in database")
                await client.send_message(chat_id=chatid,
                                          text=botCommunicationManagement.startCommandKnownTelegramID(
                                              userID=participant.accountName))

        except Exception as e:
            LOG.exception("Exception (in commandResponseStart): " + str(e))
            return

    async def commandResponseStatus(self, client: Client, message):
        try:
            LOG.success("Response on command 'status' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            database: Database = Database()
            if isinstance(message.chat.username, str):
                LOG.debug("Username exists: " + str(message.chat.username))

            participant: Participant = database.getParticipantByTelegramID(telegramID=message.chat.username)

            # reply_markup=inlineReplyMarkup, disable_web_page_preview=disableWebPagePreview

            #add user to known users
            knownUserData: KnownUserData = KnownUserData(database=database)
            knownUserData.setKnownUser(botName=telegram_bot_name, telegramID=message.chat.username, isKnown=True)

            botCommunicationManagement: BotCommunicationManagement = BotCommunicationManagement()
            telegramID: str = "@" + str(message.chat.username) if message.chat.username is not None else None
            if participant is None:
                LOG.error("Participant not found in database")
                await client.send_message(chat_id=chatid,
                                          text=botCommunicationManagement.startCommandNotKnownTelegramID(
                                              telegramID=telegramID),
                                          reply_markup=InlineKeyboardMarkup(
                                              inline_keyboard=
                                              [
                                                  [
                                                      InlineKeyboardButton(
                                                          text=botCommunicationManagement.startCommandNotKnownTelegramIDButtonText(),
                                                          url=eden_support_url),

                                                  ]
                                              ]
                                          )
                                          )

            else:
                LOG.debug("Participant found in database")
                await client.send_message(chat_id=chatid,
                                          text=botCommunicationManagement.startCommandKnownTelegramID(
                                              userID=participant.accountName))

        except Exception as e:
            LOG.exception("Exception (in commandResponseStart): " + str(e))
            return

    async def commandResponseDonate(self, client: Client, message):
        try:
            LOG.success("Response on command 'info' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            botCommunicationManagement: BotCommunicationManagement = BotCommunicationManagement()
            await client.send_message(chat_id=chatid,
                                      text=botCommunicationManagement.donateCommandtext(),
                                      reply_markup=InlineKeyboardMarkup(
                                          inline_keyboard=
                                          [
                                              [
                                                  InlineKeyboardButton(
                                                      text=botCommunicationManagement.donateCommandtextButon(),
                                                      url=pomelo_grants_url),

                                              ]
                                          ]
                                      )
                                      )
        except Exception as e:
            LOG.exception("Exception (in commandResponseStart): " + str(e))
            return


    async def commandResponseAdmin(self, client: Client, message):
        try:

            LOG.success("Response on command 'Admin' from user: " + str(message.from_user.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            # if new member is a bot do nothing
            if message.from_user.is_bot:
                LOG.debug("...is bot. Do nothing")
                return
            result = await client.promote_chat_member(chat_id=chatid,
                                                      user_id=message.from_user.username,
                                                      privileges=ChatPrivileges(
                                                          can_manage_chat=True,
                                                          can_delete_messages=True,
                                                          can_manage_video_chats=True,
                                                          can_restrict_members=True,
                                                          can_promote_members=True,
                                                          can_change_info=True,
                                                          can_invite_users=True,
                                                          can_pin_messages=True,
                                                          is_anonymous=False
                                                      ))
            LOG.success("Response (promote_chat_member): " + str(result))
            wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()

            result1 = await client.send_message(chat_id=chatid,
                                                text=wellcomeMessageObject.getWellcomeMessage(
                                                    participantAccountName=str(message.from_user.username)
                                                ))
        except Exception as e:
            LOG.exception("Exception (in commandResponseStart): " + str(e))
            return

    def idle(self):
        idle()


def runPyrogram():
    comm = Communication()
    comm.start(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    # chatID = comm.createSuperGroup(name="test1", description="test1")
    # print("Newly created chat id: " + str(chatID)) #test1 - 1001893075719

    comm.sendPhoto(sessionType=SessionType.BOT,
                   chatId="test",
                   caption="test",
                   photoPath=open('../../assets/startVideoPreview1.png'))

    chatID = -1001893075719
    botID = 1
    botName = "@up_vote_demo_bot"
    userID = 1
    # first intecation



def main():
    ###########################################
    # multiprocessing
    pyogram = Process(target=runPyrogram)
    pyogram.start()
    #############################################

    while True:
        time.sleep(3)
        print("main Thread")
    i = 9


if __name__ == "__main__":
    main()
