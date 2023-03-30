import asyncio
import logging
import os
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Union, Any

import pyrogram.raw.functions.updates
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, PeerIdInvalid
from pyrogram.filters import new_chat_members
from pyrogram.handlers import MessageHandler, ChatMemberUpdatedHandler, RawUpdateHandler
from pyrogram.methods.decorators import on_chat_member_updated
from pyrogram.raw import functions
from pyrogram.raw.types import UpdatesTooLong
from pyrogram.types import Chat, InlineKeyboardMarkup, ChatPrivileges, InlineKeyboardButton, BotCommand, Message

from constants.parameters import *
from database import Database
from database.participant import Participant
from database.room import Room
from dateTimeManagement import DateTimeManagement
from knownUserManagement import KnownUserData
from log.log import Log

from multiprocessing import Process

from pyrogram import Client, emoji, filters, types, idle, raw

from transmission.name import ADD_AT_SIGN_IF_NOT_EXISTS, REMOVE_AT_SIGN_IF_EXISTS

import time

from text.textManagement import GroupCommunicationTextManagement, Button, BotCommunicationManagement, \
    WellcomeMessageTextManagement, VideCallTextManagement, CommandResponseTextManagement


# logging.basicConfig(level=logging.DEBUG)
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


class CustomMember:
    def __init__(self, userId: str, isBot: bool = False, username: str = None):
        assert isinstance(userId, str), "userId should be str"
        assert isinstance(isBot, bool), "isBot should be bool"
        assert isinstance(username, (str, type(None))), "username should be str or None"
        self.userId = userId
        self.username = username
        self.isBot = isBot

    def __str__(self):
        return "CustomMember(userId=" + str(self.userId) + \
               ", isBot=" + "True" if self.isBot else "False" + \
                                                      ", username=" + str(
            self.username) if self.username is not None else "None" + ")"


class CommunicationException(Exception):
    pass


LOG = Log(className="Communication")

DATABASE_CONST = None


class Communication():
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
        # threading.Thread.__init__(self, daemon=True)

    # def run(self):
    #    self.idle()

    def startComm(self, apiId: int, apiHash: str, botToken: str):
        assert isinstance(apiId, int), "ApiId should be int"
        assert isinstance(apiHash, str), "ApiHash should be str"
        assert isinstance(botToken, str), "BotToken should be str"
        LOG.debug("Starting communication sessions..")
        try:
            # self.startCommAsyncSession(apiId=apiId, apiHash=apiHash, botToken=botToken)

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
                BotCommand("admin", "Promote yourself to admin in groups created by Up Vote Bot"),
                BotCommand("recording", "Get the help for the recording feature")])

            self.isInitialized = True
            LOG.debug("... done!")
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise CommunicationException("Exception: " + str(e))

    def startCommAsyncSession(self, apiId: int, apiHash: str, botToken: str):
        LOG.info("Start async bot session - event driven actions")
        # self.startSession(sessionType=SessionType.BOT_THREAD)
        self.pyrogram = Process(target=self.startSessionAsync,
                                name="Pyrogram event handler",
                                args=(apiId, apiHash, botToken))
        self.pyrogram.start()
        # asyncio.run(self.startSessionAsync(apiId=apiId, apiHash=apiHash, botToken=botToken))
        # task1 = asyncio.run(self.startSessionAsync(apiId=apiId, apiHash=apiHash, botToken=botToken))
        kva = 8

    def startSessionAsync(self, apiId: int, apiHash: str, botToken: str):
        try:
            self.setSession(sessionType=SessionType.BOT_THREAD,
                            client=Client(name=communication_session_name_async_bot + "1",
                                          api_id=apiId,
                                          api_hash=apiHash,
                                          bot_token=botToken),
                            )

            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.wellcomeProcedure,
                               filters=filters.new_chat_members), group=2
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
                MessageHandler(callback=self.actionVideoStarted,
                               filters=filters.video_chat_started), group=2
            )

            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.actionVideoEnded,
                               filters=filters.video_chat_ended), group=2
            )

            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.callFeature,
                               filters=filters.command(commands=["call"])), group=2)

            # self.sessionBotThread.add_handler(
            #    MessageHandler(callback=self.commandResponseRecording,
            #                   filters=filters.command(commands=["recording"]) & (filters.group | filters.private)),
            #                   group=2
            # )

            # maybe we can detect why stop is called
            # https://stackoverflow.com/questions/69303731/pyrogram-stops-handle-updates-after-updatestoolong-response
            self.sessionBotThread.add_handler(
                RawUpdateHandler(callback=self.rawUpdateHandler), group=1)

            # self.sessionBotThread.add_handler(
            #    MessageHandler(callback=self.commandResponseAdmin,
            #                   filters=filters.command(commands=["admin"])), group=1
            # )

            self.sessionBotThread.start()
            idle()

        except Exception as e:
            LOG.exception("Communication.startSessionAsync exception: " + str(e))

    def addKnownUserAndUpdateLocal(self, botName: str, chatID: int):
        assert isinstance(botName, str), "BotName should be str"
        assert isinstance(chatID, (int, str)), "chatID should be int or str"
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

    async def sendPhotoAsync(self,
                             client: Client,
                             chatId: (str, int),
                             photoPath: str,
                             caption: str = None,
                             replyMarkup: InlineKeyboardMarkup = None):
        try:
            assert isinstance(client, Client), "Client should be Client"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(photoPath, str), " photoPath should be str"
            assert isinstance(caption, (str, type(None))), "Caption should be str or None"
            assert isinstance(replyMarkup, (InlineKeyboardMarkup, type(None))), \
                "replyMarkup should be InlineKeyboardMarkup or None"
            LOG.info("Sending photo (async) to: " + str(chatId))

            if isinstance(chatId, type(None)) or \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return False

            response = await client.send_photo(chat_id=chatId,
                                               photo=open(photoPath, 'rb'),
                                               caption=caption,
                                               reply_markup=replyMarkup)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendPhoto-async) Waiting time (in seconds): " + str(e.value))
            LOG.debug("Sleeping for " + str(e.value) + " seconds")
            time.sleep(e.value)
            LOG.debug("Sleeping for " + str(e.value) + " seconds finished... Send message again")
            return await self.sendPhoto(client=client,
                                        chatId=chatId,
                                        photoPath=photoPath,
                                        caption=caption,
                                        replyMarkup=replyMarkup
                                        )
        except Exception as e:
            LOG.exception("Exception (in sendPhoto-async): " + str(e))

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
            assert isinstance(replyMarkup, (InlineKeyboardMarkup, type(None))), \
                "replyMarkup should be InlineKeyboardMarkup or None"
            LOG.info("Sending photo to: " + str(chatId))

            if isinstance(chatId, type(None)) or \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return False

            if sessionType == SessionType.BOT:
                response = self.sessionBot.send_photo(chat_id=chatId,
                                                      photo=open(photoPath, 'rb'),
                                                      caption=caption,
                                                      reply_markup=replyMarkup)
            elif sessionType == SessionType.USER:
                response = self.sessionUser.send_photo(chat_id=chatId,
                                                       photo=open(photoPath, 'rb'),
                                                       caption=caption,
                                                       reply_markup=replyMarkup)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except PeerIdInvalid:
            LOG.exception("Exception (in sendPhoto): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendPhoto) Waiting time (in seconds): " + str(e.value))
            LOG.debug("Sleeping for " + str(e.value) + " seconds")
            time.sleep(e.value)
            LOG.debug("Sleeping for " + str(e.value) + " seconds finished... Send message again")
            return self.sendPhoto(sessionType=sessionType,
                                  chatId=chatId,
                                  photoPath=photoPath,
                                  caption=caption,
                                  replyMarkup=replyMarkup)
        except Exception as e:
            LOG.exception("Exception (in sendPhoto): " + str(e))

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
            assert isinstance(text, str), "Text should be str"
            assert isinstance(disableWebPagePreview, bool), "disableWebPagePreview should be bool"
            assert isinstance(scheduleDate, (datetime, type(None))), "scheduleDate should be datetime or None"

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
            elif sessionType == SessionType.USER:
                response = self.sessionUser.send_message(chat_id=chatId,
                                                         text=text,
                                                         schedule_date=scheduleDate,
                                                         reply_markup=inlineReplyMarkup,
                                                         disable_web_page_preview=disableWebPagePreview)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except PeerIdInvalid:
            LOG.exception("Exception (in sendMessage): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendMessage) Waiting time (in seconds): " + str(e.value))
            LOG.debug("Sleeping for " + str(e.value) + " seconds")
            time.sleep(e.value)
            LOG.debug("Sleeping for " + str(e.value) + " seconds finished... Send message again")
            return self.sendMessage(sessionType=sessionType,
                                    chatId=chatId,
                                    text=text,
                                    disableWebPagePreview=disableWebPagePreview,
                                    scheduleDate=scheduleDate,
                                    inlineReplyMarkup=inlineReplyMarkup)
        except Exception as e:
            LOG.exception("Exception in send messages: " + str(e))
            return False

    async def sendMessageAsync(self,
                               client: Client,
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
            assert isinstance(client, Client), "Client should be Client"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(text, str), "Text should be str"
            assert isinstance(disableWebPagePreview, bool), "disableWebPagePreview should be bool"
            assert isinstance(scheduleDate, (datetime, type(None))), "scheduleDate should be datetime or None"
            assert isinstance(inlineReplyMarkup, (InlineKeyboardMarkup, type(None))), \
                "inlineReplyMarkup should be InlineKeyboardMarkup or None"

            response = await client.send_message(chat_id=chatId,
                                                 text=text,
                                                 schedule_date=scheduleDate,
                                                 reply_markup=inlineReplyMarkup,
                                                 disable_web_page_preview=disableWebPagePreview)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except PeerIdInvalid:
            LOG.exception("Exception (in sendMessage): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendMessage) Waiting time (in seconds): " + str(e.value))
            LOG.debug("Sleeping for " + str(e.value) + " seconds")
            time.sleep(e.value)
            LOG.debug("Sleeping for " + str(e.value) + " seconds finished... Send message again")
            return await self.sendMessageAsync(client=client,
                                               chatId=chatId,
                                               text=text,
                                               disableWebPagePreview=disableWebPagePreview,
                                               scheduleDate=scheduleDate,
                                               inlineReplyMarkup=inlineReplyMarkup)
        except Exception as e:
            LOG.exception("Exception in send messages - async: " + str(e))
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
            LOG.exception("Exception (in sendInvitationLink): PeerIdInvalid")
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

            self.sessionUser.archive_chats(chat_id=chatId)
            return True
        except PeerIdInvalid:
            LOG.exception("Exception (in archive group): PeerIdInvalid")
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
            if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                    telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return False

            self.sessionUser.delete_supergroup(chat_id=chatId)
            # remove also from known users
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return True
        except PeerIdInvalid:
            LOG.exception("Exception (in deleteGroup): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except Exception as e:
            LOG.exception("Exception (in deleteGroup): " + str(e))
            return False

    def leaveChat(self, sessionType: SessionType, chatId: (str, int), userId: str) -> bool:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        assert isinstance(userId, str), "UserId should be str"
        try:
            # delete option not used, because it is not working on supergroups
            LOG.debug("User" + str(userId) + " is leaving chat: " + str(chatId))
            if sessionType == SessionType.USER:
                self.sessionUser.leave_chat(chat_id=chatId)
            else:
                self.sessionBot.leave_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in leaveChat): " + str(e))
            return False

    def getMembersInGroup(self, sessionType: SessionType, chatId: (str, int)) -> list[CustomMember]:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        LOG.info("Getting members in group: " + str(chatId))
        try:
            if sessionType == SessionType.BOT and \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return []
            if sessionType == SessionType.USER:
                membersTG = self.sessionUser.get_chat_members(chat_id=chatId)
            else:
                membersTG = self.sessionBot.get_chat_members(chat_id=chatId)

            members: list[CustomMember] = []
            for member in membersTG:
                members.append(CustomMember(userId=str(member.user.id),
                                            isBot=member.user.is_bot,
                                            username=member.user.username))

            return members
        except PeerIdInvalid:
            LOG.exception("Exception (in getMembersInGroup): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return []
        except Exception as e:
            LOG.exception("Exception (in getMembersInGroup): " + str(e))
            return []

    def addChatMembers(self, chatId: (str, int), participants: list) -> bool:
        LOG.info("Adding participants to group: " + str(chatId) + " with participants: " + str(participants))
        try:
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert participants is not None, "Participants should not be null"

            knownParticipants = []
            for participant in participants:
                # here we operate with sessionUser, but we use the check if user interacted with bot - minimization of
                # probability of being kicked
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
                        result = self.sessionUser.promote_chat_member(chat_id=chatId,
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
                        LOG.success("Response (promote_chat_member): " + str(result))
                        wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()
                        self.sendMessage(chatId=chatId,
                                         sessionType=SessionType.BOT,
                                         text=wellcomeMessageObject.getWellcomeMessage(
                                             participantAccountName=str(participant)),
                                         disableWebPagePreview=True)

                    else:
                        if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                                telegramID=str(participant)):
                            result = self.sessionBot.promote_chat_member(chat_id=chatId,
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
                            LOG.success("Response (promote_chat_member): " + str(result))
                            wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()
                            self.sendMessage(chatId=chatId,
                                             sessionType=SessionType.BOT,
                                             text=wellcomeMessageObject.getWellcomeMessage(
                                                 participantAccountName=str(participant)),
                                             disableWebPagePreview=True)
                except Exception as e:
                    LOG.exception("Exception (in promoteMembers): " + str(e))
            return True
        except Exception as e:
            LOG.exception("Exception (in promoteMembers): " + str(e))
            return False

    def setChatTitle(self, chatId: (str, int), title: str) -> bool:
        try:
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(title, str), "Title should be str"
            LOG.info("Setting description to group: " + str(chatId) + " with description: " + str(title))
            self.sessionUser.set_chat_title(chat_id=chatId,
                                            title=title)
            return True
        except Exception as e:
            LOG.exception("Exception (in setChatDescription): " + str(e))
            return False

    def setChatDescription(self, chatId: (str, int), description: str) -> bool:
        try:
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(description, str), "Title should be str"
            LOG.info("Setting description to group: " + str(chatId) + " with description: " + str(description))
            self.sessionUser.set_chat_description(chat_id=chatId,
                                                  description=description)
            return True
        except Exception as e:
            LOG.exception("Exception (in setChatDescription): " + str(e))
            return False

    async def isVideoCallRunning(self, sessionType: SessionType, chatId: (str, int)) -> bool:
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            LOG.info("Checking if video call is running in group: " + str(chatId))

            groupData = await self.sessionBot.invoke(pyrogram.raw.functions.channels.GetFullChannel(
                channel=(await self.sessionBot.resolve_peer(chatId))))

            isCall = groupData.full_chat.call

            if isCall is None:
                LOG.info("No video call is running in the group " + str(chatId))
                return False
            else:
                LOG.info("Video call is running in the group " + str(chatId))
                return True
        except Exception as e:
            LOG.exception("Exception (in isVideoCallRunning): " + str(e))
            return None

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
            LOG.exception("Exception (in leaveChat): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return False
        except Exception as e:
            LOG.exception("Exception (in leaveChat): " + str(e))
            return False

    #
    # Filters management
    #

    async def wellcomeProcedure1(self, client: Client, message):
        try:
            chatid = message.chat.id
            LOG.success("New chat member: " + str(message.new_chat_members) + " in group " + str(chatid))
            database: Database = self.database

            if self.knownUserData.getKnownUsersOptimizedOnlyBoolean \
                        (botName=telegram_bot_name, telegramID=str(chatid)) is False:
                #does this really matter? Message comes when you creating a group ( + add user in process) and group
                # is not known to bot yet
                LOG.error("Group not known to bot! Does not matter if you are creating a group")
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

                    # if newMember.id is None or self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name, telegramID=str(newMember.username.lower())) is False:
                    #    continue

                    await client.send_message(chat_id=chatid,
                                              text="start")
                    result = await client.promote_chat_member(chat_id=chatid,
                                                              user_id=newMember.id,
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
                    await client.send_message(chat_id=chatid,
                                              text=str(result))

                    await client.send_message(chat_id=newMember.id,
                                              text="kva")
                else:
                    LOG.success("New member is not instance of 'User'")
        except Exception as e:
            LOG.exception("Exception (in wellcomeProcedure): " + str(e))
            return

    async def wellcomeProcedure(self, client: Client, message):  # works on demo day
        try:
            chatid = message.chat.id
            LOG.success("New chat member: " + str(message.new_chat_members) + " in group " + str(chatid))
            database: Database = self.database

            if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name, telegramID=str(chatid)) \
                    is False:
                LOG.error("Group not known to bot!")
            for newMember in message.new_chat_members:
                if isinstance(newMember, types.User):
                    LOG.success("Wellcome message to user: " + str(newMember.id))
                    LOG.debug(", username: " + str(newMember.username) if newMember.username is not None else "None"
                                                                                                              + ", name: " + str(
                        newMember.first_name) if newMember.first_name is not None else "None"
                                                                                       + ", last name: " + str(
                        newMember.last_name) if newMember.last_name is not None else "None")

                    # if new member is a bot do nothing
                    if newMember.is_bot:
                        LOG.debug("...is bot. Do nothing")
                        continue

                    if isinstance(newMember.username, str) or len(newMember.username) == 0:
                        LOG.error("WellcomeProcedure; New member username is None")

                    # promote only users who supposed to be in this room
                    participants: list[Participant] = database.getUsersInRoom(roomTelegramID=str(chatid))
                    # participants: list[Participant] = [Participant(telegramID="123456789", username="testuser")]
                    if participants is None:
                        LOG.error("WellcomeProcedure; No participants in this room or room not found")
                        return
                    for participant in participants:
                        if participant.telegramID is None:
                            LOG.error("WellcomeProcedure; Participant telegramID is None")
                            continue

                        participant.telegramID = REMOVE_AT_SIGN_IF_EXISTS(name=participant.telegramID)

                        newMemberUsername = REMOVE_AT_SIGN_IF_EXISTS(name=newMember.username)

                        if participant.telegramID.lower() == newMemberUsername.lower():
                            LOG.debug(
                                "User supposed to be in this room: " + str(participant.telegramID) + " - promoting!")

                            if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(
                                    botName=telegram_bot_name,
                                    telegramID=newMemberUsername.lower()) is False:
                                LOG.error("WellcomeProcedure; User " + newMemberUsername +
                                          " not known to bot - do nothing")
                                continue
                            result = await client.promote_chat_member(chat_id=chatid,
                                                                      user_id=newMember.id,
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

    async def commandResponseStart(self, client: Client, message):
        try:
            LOG.success("Response on command 'start' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            # database: Database = DATABASE_CONST
            if isinstance(message.chat.username, str):
                LOG.debug("Username exists: " + str(message.chat.username))

            participant: Participant = self.database.getParticipantByTelegramID(telegramID=message.chat.username)

            # add user to known users
            self.knownUserData.setKnownUser(botName=telegram_bot_name, telegramID=message.chat.username, isKnown=True)

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

    async def commandResponseStatus(self, client: Client, message):
        try:
            LOG.success("Response on command 'status' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            # database: Database = Database()
            if isinstance(message.chat.username, str):
                LOG.debug("Username exists: " + str(message.chat.username))

            participant: Participant = self.database.getParticipantByTelegramID(telegramID=message.chat.username)

            # add user to known users
            self.knownUserData.setKnownUser(botName=telegram_bot_name, telegramID=message.chat.username, isKnown=True)

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
            LOG.exception("Exception (in commandResponseStatus): " + str(e))

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
            LOG.exception("Exception (in commandResponseDonate): " + str(e))

    async def actionVideoStarted(self, client: Client, message: Message):
        try:
            chatId = message.chat.id
            messageLink = message.link
            LOG.success("Video started message appeared in chat: " + str(chatId))
            LOG.info("Link to the message: " + str(messageLink))

            # response only in known rooms created by bot (not in private chats or other groups)
            room: Room = self.database.getRoom(roomTelegramID=str(chatId))
            if room is None:
                LOG.error("actionVideoStarted; Room with telegramID " + str(chatId) + " not found in database")
                return
            LOG.info("actionVideoStarted; Room with telegramID " + str(chatId) + " found in database. Sending recording"
                                                                                 " message to the group/room.")

            videCallTextManagement: VideCallTextManagement = VideCallTextManagement()
            photoPaths: str = videCallTextManagement.startRecordingGetImagePaths()
            text: str = videCallTextManagement.videoHasBeenStarted()
            for index, photoPath in enumerate(photoPaths):
                # add text only to the last photo
                result = await self.sendPhotoAsync(client=client,
                                                   chatId=chatId,
                                                   photoPath=photoPath,
                                                   caption=text if index == len(photoPaths) - 1 else "")
                time.sleep(0.5)

                LOG.success("Response (actionVideoStarted): " + str(result))

        except Exception as e:
            LOG.exception("Exception (in actionVideoStarted): " + str(e))

    async def actionVideoEnded(self, client: Client, message: Message):
        try:
            chatId = message.chat.id
            messageLink = message.link
            LOG.success("Video has been ended message appeared in chat: " + str(chatId))
            LOG.info("Link to the message: " + str(messageLink))

            # response only in known rooms created by bot (not in private chats or other groups)
            room: Room = self.database.getRoom(roomTelegramID=str(chatId))
            if room is None:
                LOG.error("actionVideoEnded; Room with telegramID " + str(chatId) + " not found in database")
                return
            LOG.info("actionVideoEnded; Room with telegramID " + str(chatId) + " found in database.")

            videCallTextManagement: VideCallTextManagement = VideCallTextManagement()
            text: str = videCallTextManagement.videoHasBeenStopped()
            button: tuple(Button) = videCallTextManagement.videoHasBeenStoppedButtonText \
                (inviteLink=eden_portal_upload_video_url)

            result = await self.sendMessageAsync(client=client,
                                                 chatId=chatId,
                                                 text=text,
                                                 inlineReplyMarkup=InlineKeyboardMarkup(
                                                     inline_keyboard=
                                                     [
                                                         [
                                                             InlineKeyboardButton(text=button[0]['text'],
                                                                                  url=button[0]['value']),

                                                         ]
                                                     ]
                                                 )
                                                 )

            LOG.success("Response (actionVideoEnded): " + str(result))
        except Exception as e:
            LOG.exception("Exception (in actionVideoEnded): " + str(e))

    async def getGroupCall(self, client: Client, chat_id: Union[int, str], limit: int = 1):
        """ Get group call - not in use for now - just test for the feature in the future"""
        peer = await client.resolve_peer(chat_id)

        if isinstance(peer, raw.types.InputPeerChannel):
            call = (await client.invoke(
                raw.functions.channels.GetFullChannel(
                    channel=peer
                ))).full_chat.call
        else:
            if isinstance(peer, raw.types.InputPeerChat):
                call = (await client.invoke(
                    raw.functions.messages.GetFullChat(
                        chat_id=peer.chat_id
                    ))).full_chat.call

        if call is None:
            return call

        return await client.invoke(
            raw.functions.phone.GetGroupCall(
                call=call,
                limit=limit
            ))

    async def callFeature(self, client: Client, message: Message):
        """Not in use for now - just test for the feature in the future"""
        try:
            chatId = message.chat.id

            groupData = await client.invoke(pyrogram.raw.functions.channels.GetFullChannel(
                channel=(await client.resolve_peer(message.chat.id))))

            groupData1 = await self.sessionBotThread.invoke(pyrogram.raw.functions.channels.GetFullChannel(
                channel=(await self.sessionBotThread.resolve_peer(-1001888934788))))

            isCall = groupData.full_chat.call
            if isCall is None:
                print("No call")
                return

            # available only with UserBot
            result = await self.getGroupCall(client=client, chat_id=chatId, limit=1)
            LOG.debug("Result: " + str(result))
        except Exception as e:
            LOG.exception("Exception (in testtest): " + str(e))

    """async def commandResponseRecording(self, client: Client, message: Message):
        try:
            chatId = message.chat.id
            isPrivateChat: bool = message.chat.type == ChatType.PRIVATE
            LOG.success("Recording command appeared in chat: " + str(chatId) +
                        " (isPrivateChat: " + str(isPrivateChat) + ")")

            isPrivateChat: bool = message.chat.type == ChatType.PRIVATE
            # response only in known rooms created by bot
            room: Room = self.database.getRoom(roomTelegramID=str(chatId))
            if room is None and isPrivateChat is False:
                LOG.error("commandResponseRecording; Room with telegramID " + str(chatId) + " not found in database and"
                                                                                            "not private chat")
                return
            LOG.info("commandResponseRecording; Room with telegramID " + str(chatId) + " found in database.")

            commandResponseTextManagement: CommandResponseTextManagement = CommandResponseTextManagement()
            text: str = commandResponseTextManagement.recording()
            photoPath: str = commandResponseTextManagement.recordingImagePath()

            result = await client.send_photo(chat_id=chatId,
                                             photo=open(photoPath, 'rb'),
                                             caption=text)
            LOG.success("Response (commandResponseRecording): " + str(result))
        except Exception as e:
            LOG.exception("Exception (in commandResponseRecording): " + str(e))"""

    async def rawUpdateHandler(self, client, update, users, chats):
        """
        @YaroslavHladkyi That's an update you get. You can set up a RawUpdateHandler and use an if isinstance() to
        check for types.UpdatesTooLong. Then you could call the method from the comments in that handler to get new\
        updates again.
        """
        try:
            if isinstance(update, UpdatesTooLong):
                LOG.error("Updates too long - before getDifference call")
                pyrogram.raw.functions.updates.GetDifference()
                LOG.error("Updates too long - after getDifference call")
                return
        except Exception as e:
            LOG.exception("Exception (in rawUpdateHandler): " + str(e))

    async def commandResponseAdmin(self, client: Client, message):
        try:

            LOG.success(
                "Response on command 'Admin' from user: " + str(message.from_user.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            # if new member is a bot do nothing
            if message.from_user.is_bot:
                LOG.debug("...is bot. Do nothing")
                return
            result = await client.promote_chat_member(chat_id=chatid,
                                                      user_id=message.from_user.id,
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
            LOG.exception("Exception (in commandResponseAdmin): " + str(e))

    def idle(self):
        idle()


def runPyrogram():
    comm = Communication()
    comm.start(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    # chatID = comm.createSuperGroup(name="test1", description="test1")
    # print("Newly created chat id: " + str(chatID)) #test1 - 1001893075719

    # comm.sendPhoto(sessionType=SessionType.BOT,
    #               chatId="test",
    #               caption="test",
    #               photoPath=open('../../assets/startVideoPreview1.png'))

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
