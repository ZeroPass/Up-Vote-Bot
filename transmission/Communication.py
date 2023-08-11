from datetime import datetime, timedelta
from enum import Enum
from typing import Union

import pyrogram.raw.functions.updates
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from pyrogram.errors import FloodWait, PeerIdInvalid, ChatAdminRequired
from pyrogram.handlers import MessageHandler, RawUpdateHandler, InlineQueryHandler, CallbackQueryHandler, \
    ChosenInlineResultHandler
from pyrogram.raw.types import UpdatesTooLong, UpdateBotCallbackQuery, UpdateBotInlineSend
from pyrogram.types import Chat, InlineKeyboardMarkup, ChatPrivileges, InlineKeyboardButton, BotCommand, Message, \
    ChatPreview, InlineQuery, CallbackQuery, ChosenInlineResult
from pyrogram.utils import pack_inline_message_id

from chain.dfuse import Response, ResponseError
from constants.rawActionWeb import RawActionWeb
#from chain.electionStateObjects import CurrentElectionStateHandlerActive
from database.comunityParticipant import CommunityParticipant
from transmissionCustom import REMOVE_AT_SIGN_IF_EXISTS, MemberStatus, PARSE_TG_NAME, ADD_AT_SIGN_IF_NOT_EXISTS
from constants.parameters import *
from database import Database, KnownUser, Election
from database.participant import Participant
from database.room import Room
from knownUserManagement import KnownUserData
from log.log import Log
from chain.eden import EdenData

from multiprocessing import Process

from pyrogram import Client, filters, types, idle, raw



import time

from text.textManagement import Button, BotCommunicationManagement, \
    WellcomeMessageTextManagement, VideCallTextManagement

from transmissionCustom import CustomMember, AdminRights, Promotion

class SessionType(Enum):
    USER = 1
    BOT = 2
    BOT_THREAD = 3


class CommunicationException(Exception):
    pass


LOG = Log(className="Communication")

DATABASE_CONST = None


class Communication:
    # sessions = {}
    sessionUser: Client = None
    sessionBot: Client = None
    sessionBotThread: Client = None
    isInitialized: bool = False
    pyrogram: Process = None

    def __init__(self, database: Database, edenData: EdenData):
        assert isinstance(database, Database), "Database should be Database"
        LOG.info("Init communication")
        self.database = database
        global DATABASE_CONST
        DATABASE_CONST = database
        self.knownUserData: KnownUserData = KnownUserData(database=database)

        #we need it for the SBT call on bot
        self.edenData: EdenData = edenData
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
                BotCommand("vote", "Create link to vote for a participant(only when election is running)"),
                BotCommand("donate", "Support the development of Up Vote Bot features"),
                BotCommand("chatid", "Get current chat id (admin + (super)group only)"),
                BotCommand("check", "Check if user is known to bot (use with parameter <account name> or <telegram id>) (private chat only)"),
                BotCommand("unknown_users", "List of participants that will participate in next election, but not known to bot (private chat + admin only)"),
                BotCommand("not_active_sbt_users","List of participants wits SBTs, but not in community group (private chat + admin only)"),
            ])

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
                MessageHandler(callback=self.commandResponseVote,
                               filters=filters.command(commands=["vote"]) & filters.private), group=2
            )

            self.sessionBotThread.add_handler(
                CallbackQueryHandler(callback=self.inlineQueryVote), group=2
            )

            """self.sessionBotThread.add_handler(
                ChosenInlineResultHandler(callback=self.inlineQueryVote1),
            group=2)"""


            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.commandResponseGetChatID,
                               filters=filters.command(commands=["chatID"]) & filters.group), group=2
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

            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.commandResponseCheck,
                               filters=filters.command(commands=["check"]) & filters.private), group=2)

            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.commandResponseCheckParticipants,
                                    filters=filters.command(commands=["unknown_users"]) & filters.private), group=2)

            self.sessionBotThread.add_handler(
                MessageHandler(callback=self.commandResponseCheckParticipantsSBT,
                                    filters=filters.command(commands=["not_active_sbt_users"]) & filters.private), group=2)

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
            LOG.success("Pyrogram event handler started")
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
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(text, str), "Text should be str"
            assert isinstance(disableWebPagePreview, bool), "disableWebPagePreview should be bool"
            assert isinstance(scheduleDate, (datetime, type(None))), "scheduleDate should be datetime or None"

            assert (sessionType is SessionType.BOT) or \
                   (sessionType is SessionType.USER and inlineReplyMarkup is None), \
                "when SessionType is USER there is no option to send inlineReplyMarkup!"

            scheduleText: str = str(scheduleDate) if scheduleDate is not None else "<now>"
            LOG.info("Send message to: " + str(chatId) + " with text: " + text
                     + " and scheduleDate: " + scheduleText)

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
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=str(chatId))
            return True
        except PeerIdInvalid:
            LOG.exception("Exception (in deleteGroup): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=str(chatId))
            return False
        except Exception as e:
            LOG.exception("Exception (in deleteGroup): " + str(e))
            return False

    def removeUserFromGroup(self,  sessionType: SessionType, chatId: (str, int), userId: str) -> bool:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        assert isinstance(userId, str), "userId should be str"
        LOG.info("Removing user: " + str(userId) + " from group: " + str(chatId))
        try:
            #if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
            #                                                        telegramID=str(chatId)) is False:
            #    LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
            #    return False
            if sessionType == SessionType.USER:
                toReturn: bool = self.sessionUser.ban_chat_member(chat_id=chatId,
                                             user_id=userId,
                                             until_date=datetime.now() + timedelta(minutes=1))
            else:
                toReturn: bool = self.sessionBot.ban_chat_member(chat_id=chatId,
                                             user_id=userId,
                                             until_date=datetime.now() + timedelta(minutes=1))
            return toReturn
        except PeerIdInvalid:
            LOG.exception("Exception (in removeUserFromGroup): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=str(chatId))
            return False
        except Exception as e:
            LOG.exception("Exception (in removeUserFromGroup): " + str(e))
            return False

    def getGeneralChatLink(self, sessionType: SessionType, chatId: (str, int)) -> str:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        try:
            # we use this function to get same chat link (export_chat_invite_link always generates new link)
            LOG.debug("Getting general chat link for chat: " + str(chatId))
            if sessionType == SessionType.USER:
                chat = self.sessionUser.get_chat(chat_id=chatId)
            else:
                chat = self.sessionBot.get_chat(chat_id=chatId)

            if isinstance(chat, types.Chat) is False:
                raise Exception("Chat is not a Chat object. Probably user/bot is not a member of the chat.")

            if chat.invite_link is None:
                raise Exception("Chat link is None.")

            return chat.invite_link
        except Exception as e:
            LOG.exception("Exception (in getGeneralChatLink): " + str(e))
            return None

    def leaveChat(self, sessionType: SessionType, chatId: (str, int), userId: str) -> bool:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        try:
            # delete option not used, because it is not working on supergroups
            LOG.debug("User is leaving a chat: " + str(chatId))
            if sessionType == SessionType.USER:
                self.sessionUser.leave_chat(chat_id=chatId)
            else:
                self.sessionBot.leave_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in leaveChat): " + str(e))
            return False

    def getMemberInGroup(self, sessionType: SessionType, chatId: int, userId: (str, int)) -> CustomMember:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, int), "ChatId should be int"
        assert isinstance(userId, (str, int)), "UserId should be str or int"
        LOG.debug("Getting member in group: " + str(chatId) + " with userId: " + str(userId))
        try:
            if sessionType == SessionType.BOT and \
                    self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return None
            member = None
            if sessionType == SessionType.USER:
                member = self.sessionUser.get_chat_member(chat_id=chatId,
                                                             user_id=userId)
            else:
                member = self.sessionBot.get_chat_member(chat_id=chatId,
                                                            user_id=userId)

            if member is None:
                LOG.error("Member not found in group: " + str(chatId))
                return None

            if member.status is ChatMemberStatus.OWNER or member.status is ChatMemberStatus.ADMINISTRATOR:
                LOG.debug("Member is admin in group: " + str(chatId))
                adminRights = AdminRights(isAdmin=True,
                                            canChangeInfo=member.privileges.can_change_info,
                                            canDeleteMessages=member.privileges.can_delete_messages,
                                            canEditMessages=member.privileges.can_edit_messages,
                                            canInviteUsers=member.privileges.can_invite_users,
                                            canManageChat=member.privileges.can_manage_chat,
                                            canManageVideoChats=member.privileges.can_manage_video_chats,
                                            canPinMessages=member.privileges.can_pin_messages,
                                            canPostMessages=member.privileges.can_post_messages,
                                            canPromoteMembers=member.privileges.can_promote_members,
                                            canRestrictMembers=member.privileges.can_restrict_members,
                                            isAnonymous=member.privileges.is_anonymous)

                promotedBy = member.promoted_by
                promotion: Promotion = Promotion(userId=str(promotedBy.id), username=promotedBy.username)
                memberStatus: MemberStatus = MemberStatus.ADMINISTRATOR if member.status \
                                             is pyrogram.enums.ChatMemberStatus.OWNER else MemberStatus.OWNER
            else:
                LOG.debug("Member is not admin in group: " + str(chatId))
                adminRights = AdminRights(isAdmin=False)
                promotion: Promotion = None
                memberStatus: MemberStatus = MemberStatus.MEMBER




            cm: CustomMember = CustomMember(userId=str(member.user.id),
                                            memberStatus=memberStatus,
                                            isBot=member.user.is_bot,
                                            username=member.user.username,
                                            tag=member.custom_title,
                                            adminRights=adminRights,
                                            promotedBy=promotion)

            return cm
        except Exception as e:
            LOG.exception("Exception (in getMemberInGroup): " + str(e))
            return None

    async def getMembersInGroupS(self, client: Client, chatId: (str, int)) -> list[CustomMember]:
        assert isinstance(client, Client), "client should be Client"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        try:
            LOG.info("Getting members in group(s): " + str(chatId))
            if self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                         telegramID=str(chatId)) is False:
                LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                return []
            membersTG = client.get_chat_members(chat_id=chatId)


            members: list[CustomMember] = []
            async for member in membersTG:
                if member.user.is_bot:
                    LOG.trace("Skipping bot: " + str(member.user.id) + " in group: " + str(chatId))
                    continue


                if member.status is ChatMemberStatus.OWNER or member.status is ChatMemberStatus.ADMINISTRATOR:
                    LOG.debug("Member is admin in group: " + str(chatId))
                    adminRights = AdminRights(isAdmin=True,
                                              canChangeInfo=member.privileges.can_change_info,
                                              canDeleteMessages=member.privileges.can_delete_messages,
                                              canEditMessages=member.privileges.can_edit_messages,
                                              canInviteUsers=member.privileges.can_invite_users,
                                              canManageChat=member.privileges.can_manage_chat,
                                              canManageVideoChats=member.privileges.can_manage_video_chats,
                                              canPinMessages=member.privileges.can_pin_messages,
                                              canPostMessages=member.privileges.can_post_messages,
                                              canPromoteMembers=member.privileges.can_promote_members,
                                              canRestrictMembers=member.privileges.can_restrict_members,
                                              isAnonymous=member.privileges.is_anonymous)

                    promotedBy = member.promoted_by
                    promotion: Promotion = Promotion(userId=str(promotedBy.id), username=promotedBy.username) if \
                                            promotedBy is not None else None
                    memberStatus: MemberStatus = MemberStatus.ADMINISTRATOR if member.status \
                                                                               is pyrogram.enums.ChatMemberStatus.OWNER else MemberStatus.OWNER
                else:
                    LOG.debug("Member is not admin in group: " + str(chatId))
                    adminRights = AdminRights(isAdmin=False)
                    promotion: Promotion = None
                    memberStatus: MemberStatus = MemberStatus.MEMBER

                members.append(CustomMember(userId=str(member.user.id),
                                            memberStatus=memberStatus,
                                            isBot=member.user.is_bot,
                                            username=member.user.username,
                                            tag=member.custom_title,
                                            adminRights=adminRights,
                                            promotedBy=promotion))

            return members
        except PeerIdInvalid:
            LOG.exception("Exception (in getMembersInGroup): PeerIdInvalid")
            self.knownUserData.removeKnownUser(botName=telegram_bot_name, telegramID=chatId)
            return []
        except Exception as e:
            LOG.exception("Exception (in getMembersInGroup): " + str(e))
            return []

    def getMembersInGroup(self, sessionType: SessionType, chatId: (str, int)) -> list[CustomMember]:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, (str, int)), "ChatId should be str or int"
        try:
            LOG.info("Getting members in group: " + str(chatId))
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
                if member.user.is_bot:
                    LOG.trace("Skipping bot: " + str(member.user.id) + " in group: " + str(chatId))
                    continue


                if member.status is ChatMemberStatus.OWNER or member.status is ChatMemberStatus.ADMINISTRATOR:
                    LOG.debug("Member is admin in group: " + str(chatId))
                    adminRights = AdminRights(isAdmin=True,
                                              canChangeInfo=member.privileges.can_change_info,
                                              canDeleteMessages=member.privileges.can_delete_messages,
                                              canEditMessages=member.privileges.can_edit_messages,
                                              canInviteUsers=member.privileges.can_invite_users,
                                              canManageChat=member.privileges.can_manage_chat,
                                              canManageVideoChats=member.privileges.can_manage_video_chats,
                                              canPinMessages=member.privileges.can_pin_messages,
                                              canPostMessages=member.privileges.can_post_messages,
                                              canPromoteMembers=member.privileges.can_promote_members,
                                              canRestrictMembers=member.privileges.can_restrict_members,
                                              isAnonymous=member.privileges.is_anonymous)

                    promotedBy = member.promoted_by
                    promotion: Promotion = Promotion(userId=str(promotedBy.id), username=promotedBy.username) if \
                        promotedBy is not None else None
                    memberStatus: MemberStatus = MemberStatus.ADMINISTRATOR if member.status \
                                                                               is pyrogram.enums.ChatMemberStatus.ADMINISTRATOR else MemberStatus.OWNER
                else:
                    LOG.debug("Member is not admin in group: " + str(chatId))
                    adminRights = AdminRights(isAdmin=False)
                    promotion: Promotion = None
                    memberStatus: MemberStatus = MemberStatus.MEMBER

                members.append(CustomMember(userId=str(member.user.id),
                                            memberStatus=memberStatus,
                                            isBot=member.user.is_bot,
                                            username=member.user.username,
                                            tag=member.custom_title,
                                            adminRights=adminRights,
                                            promotedBy=promotion))

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

    def promoteSpecificMember(self, sessionType: SessionType, chatId: (str, int), userId: (str, int),#  participant: Participant,
                              adminRights: AdminRights) -> bool:
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(userId, (str, int)), "userId should be str or int"
            #assert isinstance(participant, Participant), "participant should be a Participant object"
            assert isinstance(adminRights, AdminRights), "adminRights should be an AdminRights object"
            LOG.info("Promoting specific participant in group: " + str(chatId) + " with user id: " + str(userId))

            if sessionType == SessionType.BOT:
                if isinstance(chatId, type(None)) or \
                        self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                             telegramID=str(chatId)) is False:
                    LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                    return False

            # remove from admin list
            promote: bool = False
            if adminRights.isAdmin == True:
                promote = True
                LOG.debug("Promote particiopant to admin")
            else:
                LOG.debug("Remove participant from admin list")

            if sessionType == SessionType.USER:
                result = self.sessionUser.promote_chat_member(chat_id=chatId,
                                                              user_id=userId,
                                                              privileges=ChatPrivileges(
                                                                  can_manage_chat=adminRights.canManageChat,
                                                                  can_delete_messages=adminRights.canDeleteMessages,
                                                                  can_manage_video_chats=adminRights.canManageVideoChats,
                                                                  can_restrict_members=adminRights.canRestrictMembers,
                                                                  can_promote_members=adminRights.canPromoteMembers,
                                                                  can_change_info=adminRights.canChangeInfo,
                                                                  can_invite_users=adminRights.canInviteUsers,
                                                                  can_pin_messages=adminRights.canPinMessages,
                                                                  is_anonymous=adminRights.isAnonymous
                                                              )
                                                              ) if promote is True else \
                    self.sessionUser.promote_chat_member(chat_id=chatId,
                                                              user_id=userId,
                                                              privileges=ChatPrivileges(
                                                                  can_manage_chat=False,
                                                                  can_delete_messages=False,
                                                                  can_manage_video_chats=False,
                                                                  can_restrict_members=False,
                                                                  can_promote_members=False,
                                                                  can_change_info=False,
                                                                  can_invite_users=False,
                                                                  can_pin_messages=False,
                                                                  is_anonymous=False
                                                              )
                                                              )

                LOG.success("Response (promoteSpecificMember): " + str(result))

            else:
                    result = self.sessionBot.promote_chat_member(chat_id=chatId,
                                                                  user_id=userId,
                                                                  privileges=ChatPrivileges(
                                                                      can_manage_chat=adminRights.canManageChat,
                                                                      can_delete_messages=adminRights.canDeleteMessages,
                                                                      can_manage_video_chats=adminRights.canManageVideoChats,
                                                                      can_restrict_members=adminRights.canRestrictMembers,
                                                                      can_promote_members=adminRights.canPromoteMembers,
                                                                      can_change_info=adminRights.canChangeInfo,
                                                                      can_invite_users=adminRights.canInviteUsers,
                                                                      can_pin_messages=adminRights.canPinMessages,
                                                                      is_anonymous=adminRights.isAnonymous
                                                                  )
                                                                  ) if promote is True else \
                        self.sessionBot.promote_chat_member(chat_id=chatId,
                                                             user_id=userId,
                                                             privileges=ChatPrivileges(
                                                                 can_manage_chat=False,
                                                                 can_delete_messages=False,
                                                                 can_manage_video_chats=False,
                                                                 can_restrict_members=False,
                                                                 can_promote_members=False,
                                                                 can_change_info=False,
                                                                 can_invite_users=False,
                                                                 can_pin_messages=False,
                                                                 is_anonymous=False
                                                             )
                                                             )
                    LOG.success("Response (promoteSpecificMember): " + str(result))
            return True
        except Exception as e:
            LOG.exception("Exception (in promoteSpecificMember): " + str(e))
            return False

    def setAdministratorTitle(self, sessionType: SessionType, chatId: (str, int), userId: (str, int), title: str) -> bool:
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            assert isinstance(userId, (str, int)), "userId should be str or int"
            assert isinstance(title, str), "Title should be str"
            LOG.info("Setting administrator title in (super)group: " + str(chatId)
                     + " with user id: " + str(userId) + " and title: " + str(title))

            if sessionType == SessionType.BOT:
                if isinstance(chatId, type(None)) or \
                        self.knownUserData.getKnownUsersOptimizedOnlyBoolean(botName=telegram_bot_name,
                                                                             telegramID=str(chatId)) is False:
                    LOG.error("User/group " + str(chatId) + " is not known to the bot" + telegram_bot_name + "!")
                    return False

            #title can be up to 16 characters long
            if len(title) > 16:
                title = title[:16 - 3] + '...'

            if title == "":
                LOG.debug("Remove administrator title")

            if sessionType == SessionType.USER:
                self.sessionUser.set_administrator_title(chat_id=chatId,
                                                        user_id=userId,
                                                        title=title)
            else:
                self.sessionBot.set_administrator_title(chat_id=chatId,
                                                        user_id=userId,
                                                        title=title)
            return True
        except ValueError as e:
            LOG.exception("Exception (in setAdministratorTitle); ValueError : " + str(e))
            return False
        except ChatAdminRequired as e:
            LOG.exception("Exception (in setAdministratorTitle); ChatAdminRequired(maybe current user is admin but did"
                          "not raise the goal user to admin): " + str(e))
            LOG.debug("Only admin can set administrator title. And only if current admin raised the goal user to admin"
                      "can set administrator title")
            return False
        except Exception as e:
            LOG.exception("Exception (in setChatDescription): " + str(e))
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

    def isInChat(self, sessionType: SessionType, chatId: (str, int)) -> bool:
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            LOG.info("Checking if user(bot) is in chat: " + str(chatId))
            chatIdInt: int = None
            try:
                if isinstance(chatId, str):
                    chatIdInt = int(chatId)
                elif isinstance(chatId, int):
                    chatIdInt = chatId
                else:
                    raise Exception("ChatId is not str or int")
            except Exception as e:
                LOG.exception("Not int value stored in string: " + str(e))
                raise Exception("Not int value stored in string: " + str(e))


            if sessionType == SessionType.USER:
                chat = self.sessionUser.get_chat(chat_id=chatIdInt)
            else:
                chat = self.sessionBot.get_chat(chat_id=chatIdInt)

            if isinstance(chat, Chat):
                return True
            elif isinstance(chat, ChatPreview):
                return False
            else:
                raise Exception("Chat is not Chat or ChatPreview")
        except Exception as e:
            LOG.exception("Exception (in isInChat): " + str(e))
            return None

    async def isVideoCallRunning(self, sessionType: SessionType, chatId: (str, int)) -> bool:
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str or int"
            LOG.info("Checking if video call is running in group: " + str(chatId))
            chatIdInt: int = None
            try:
                if isinstance(chatId, str):
                    chatIdInt = int(chatId)
                elif isinstance(chatId, int):
                    chatIdInt = chatId
                else:
                    raise Exception("ChatId is not str or int")
            except Exception as e:
                LOG.exception("Not int value stored in string: " + str(e))
                return None

            groupData = await self.sessionBot.invoke(pyrogram.raw.functions.channels.GetFullChannel(
                channel=(await self.sessionBot.resolve_peer(chatIdInt))))

            isCall = groupData.full_chat.call

            if isCall is None:
                LOG.info("No video call is running in the group " + str(chatIdInt))
                return False
            else:
                LOG.info("Video call is running in the group " + str(chatIdInt))
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

                    if isinstance(newMember.username, str) is False or len(newMember.username) == 0:
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
            LOG.success("Response on command 'donate' from user: " + str(message.chat.username) if not None else "None")
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

    def inlineQueryVote(self, client: Client, callback_query):
        try:
            LOG.success("Inline query button pressed")
            # data should be: <vote>_<voter>_<round>
            data: list[str] = callback_query.data.split("_")
            if len(data) != 3:
                LOG.error("Data is not correct")

            candidate: str = data[0]
            voter: str = data[1]
            round: str = int(data[2])
            chatID = callback_query.message.chat.id
            messageID = callback_query.message.id

            client.edit_message_text(
                chat_id=chatID,
                message_id=messageID,
                text="Click below to vote for **" + candidate + "** on bloks.io - round " + str(round + 1) +
                     "("+ str(round) +").",
                reply_markup=InlineKeyboardMarkup([[
                                                InlineKeyboardButton(text="Vote on bloks.io",
                                                                     url=RawActionWeb().electVote(
                                                                         candidate=candidate,
                                                                         voter = voter,
                                                                         round=round
                                                                         )
                                                                     )]])
            )

        except Exception as e:
            LOG.exception("Exception (in inlineQueryVote): " + str(e))

    def getCurrentParticipant(self, election: Election, telegramID: str, round: int) -> Participant:
        assert isinstance(election, Election), "election is not a Election"
        assert isinstance(telegramID, str), "telegramID is not a string"
        assert isinstance(round, int), "round is not a int"
        try:
            LOG.debug("Get member")

            participant: Participant = self.database.getMemberByTelegramIDAndRound(election=election,
                                                                                   telegramID=telegramID,
                                                                                   round=round)
            return participant
        except Exception as e:
            LOG.exception("Exception (in getMember): " + str(e))
            return None
    def getGroupParticipants(self, election: Election, telegramID: str, round: int) -> list[Participant]:
        assert isinstance(election, Election), "election is not a Election"
        assert isinstance(telegramID, str), "telegramID is not a string"
        assert isinstance(round, int), "round is not a int"
        try:
            LOG.debug("Get group participants")

            participants: list[Participant] = self.database.getMembersFromGroup(election=election,
                                                                                telegramID=telegramID,
                                                                                round=round)
            return participants
        except Exception as e:
            LOG.exception("Exception (in getGroupParticipants): " + str(e))
            raise CommunicationException("Exception (in getGroupParticipants): " + str(e))


    async def commandResponseVote(self, client: Client, message: Message):
        try:
            LOG.success("Response on command 'vote' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            userID = message.from_user.username if message.from_user.username is not None else str(message.from_user.id)
            contract: str = eden_account
            LOG.success(".. in chat: " + str(chatid))
            demo: bool = False
            if demo:
                userID = telegram_admin_ultimate_rights_id[0]

            # before election: 319271246
            # round 1: 319277246
            # round 2: 319279246 - not participate
            edenData: Response = self.edenData.getCurrentElectionState(height= None)
                #(height=self.modeDemo.currentBlockHeight
            #if self.modeDemo is not None else None)
            if isinstance(edenData, ResponseError):
                raise CommunicationException(
                    "CommandResponseVote; Error when called eden.getCurrentElectionState; "
                    "Description: " + edenData.error)
            if isinstance(edenData.data, ResponseError):
                raise CommunicationException(
                    "commandResponseVote: Error when called eden.commandResponseVote; "
                    "Description: " + edenData.data.error)

            receivedData = edenData.data
            electionState = receivedData[0]
            data = receivedData[1]

            if electionState != "current_election_state_active":
                LOG.error("Command 'vote' is only available when election is running.")
                await client.send_message(chat_id=chatid,
                                          text="Command 'vote' is only available when election is running.")
                return None

            LOG.debug("Command 'vote' is available.")
            round: int = data["round"]

            #get running elections
            election: Election = self.database.getActiveElection(contract=contract)
            if election is None:
                LOG.error("Election not found in database")
                await client.send_message(chat_id=chatid,
                                          text="Something went wrong, please try again later.")
                return None


            #check if user is known to bot and if participate in current round
            currentParticipant: Participant = self.getCurrentParticipant(election=election,
                                                                         telegramID=userID,
                                                                         round=round)
            if currentParticipant is None:
                LOG.error("Participant is not participating in current round")
                await client.send_message(chat_id=chatid,
                                          text="Election is running but you are not participating in the current round.")
                return None

            participants: list[Participant] = self.getGroupParticipants(election=election,
                                                                        telegramID=userID,
                                                                        round=round)
            if participants is None or len(participants) < 1:
                LOG.error("Participants not found in database")
                return None

            inlineKeyboard: list[list[InlineKeyboardButton]] = []
            for participant in participants:
                inlineKeyboard.append([InlineKeyboardButton(text=participant.accountName + " (" + str(participant.telegramID) + ")",
                                                            callback_data=participant.accountName + "_" +
                                                                          currentParticipant.accountName + "_" +
                                                                          str(round))])


            await client.send_message(chat_id=chatid,
                                      text="Select the account you want to vote for:",
                                      reply_markup=InlineKeyboardMarkup(
                                          inline_keyboard=inlineKeyboard
                                      )
                                      )
        except Exception as e:
            LOG.exception("Exception (in commandResponseVote): " + str(e))

    async def commandResponseGetChatID(self, client: Client, message: Message):
        try:
            LOG.success("Response on command 'getChatID' from user: " + str(message.chat.username) if not None else "None")
            chatID = message.chat.id
            userID = message.from_user.id

            if message.reply_to_top_message_id:
                messageThreadID = message.reply_to_top_message_id
            else:
                messageThreadID = message.reply_to_message_id

            async for m in client.get_chat_members(chatID, filter=ChatMembersFilter.ADMINISTRATORS):
                try:
                    LOG.debug("Admin: " + str(m))
                    adminID = m.user.id
                    if adminID == userID:
                        self.knownUserData.setKnownUser(botName=telegram_bot_name, telegramID=message.chat.id,
                                                        isKnown=True)
                        await client.send_message(chat_id=chatID,
                                                  reply_to_message_id=messageThreadID,
                                                  text="Group's telegram ID: " + str(chatID))
                except Exception as e:
                    LOG.exception("Exception (in commandResponseGetChatID.inline for loop): " + str(e))
        except Exception as e:
            LOG.exception("Exception (in commandResponseGetChatID): " + str(e))


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

    async def commandResponseCheck(self, client: Client, message: Message):
        try:
            LOG.success("Response on command 'getChatID' from user: " + str(message.chat.username) if not None else "None")
            chatID = message.chat.id
            userID = message.from_user.id

            if  len(message.text.split(" ")) != 2:
                await client.send_message(chat_id=chatID,
                                          text="Command must be formatted: \n /check < accountName/telegram >")
                return

            accountName: str = message.text.split(" ")[1]
            if accountName == "":
                await client.send_message(chat_id=chatID,
                                          text="Command must be formatted: \n /check < accountName/telegram >")
                return

            participants: list[Participant] = self.database.getParticipantByContract(contractAccount=eden_account,
                                                                                     fromDate=datetime.now() - timedelta(
                                                                                         days=1000)
                                                                                     )
            if participants is None or len(participants) == 0:
                await client.send_message(chat_id=chatID,
                                          text="Something went wrong. No participants found in database")
                return
            for participant in participants:
                if PARSE_TG_NAME(participant.telegramID).lower() == \
                    PARSE_TG_NAME(accountName).lower():
                    #found using telegramID

                    knownUser: KnownUser =self.knownUserData.getKnownUserFromOptimized(botName=telegram_bot_name,
                                                                 telegramID=PARSE_TG_NAME(name=participant.telegramID))

                    await client.send_message(chat_id=chatID,
                                              #reply_to_message_id=messageThreadID,
                                              text="User with this telegramID ** is known** to bot. \nEden account: **"
                                                   + participant.accountName + "**"
                                              if knownUser is not None else
                                                "User with this telegramID **not known** to bot. \nEden account: **"
                                                   + participant.accountName + "**")
                    return

                elif participant.accountName.lower() == accountName.lower():
                    #found using accountName
                    knownUser: KnownUser = self.knownUserData.getKnownUserFromOptimized(botName=telegram_bot_name,
                                                                                        telegramID=PARSE_TG_NAME(
                                                                                            name=participant.telegramID))

                    await client.send_message(chat_id=chatID,
                                              # reply_to_message_id=messageThreadID,
                                              text="User with this account name is **known** to bot. \nTelegram account: **"
                                                   + participant.telegramID + "**"
                                              if knownUser is not None else
                                              "User with this account name is **not known** to bot. \nTelegram account: **"
                                                   + participant.telegramID + "**")
                    return

            await client.send_message(chat_id=chatID,
                                      # reply_to_message_id=messageThreadID,
                                      text="Given account name or telegramID not found in database")

        except Exception as e:
            LOG.exception("Exception (in commandResponseGetChatID): " + str(e))

    def cleanUsername(self, username):
        assert isinstance(username, str), "username is not a string: {}".format(username)
        # Lowercase the username and strip leading '@'
        return username.lstrip('@').lower()

    def usernameInList(self, username, userList):
        assert isinstance(username, str), "username is not a string"
        assert isinstance(userList, list), "userList is not a list"
        cleanedUsername = self.cleanUsername(username)

        # Clean all usernames in the list
        cleanedUserList = [self.cleanUsername(user) for user in userList]

        # Check if the cleaned username is in the cleaned list
        return cleanedUsername in cleanedUserList

    async def checkIfUserHasAdminRightsInGroupOrBotAdmin(self, client: Client, chatId: int, username: str):
        assert isinstance(chatId, int), "chatId is not a int"
        assert isinstance(username, str), "userId is not a str"
        try:
            LOG.debug("Check if user has admin rights in group or user is admin in bot")

            if self.usernameInList(username, telegram_admin_ultimate_rights_id):
                return True

            if self.usernameInList(username, telegram_admins_id):
                return True

            LOG.debug("Getting group members in " + str(chatId))
            groupChatMember = await client.get_chat_member(chat_id=chatId,  user_id=username)
            LOG.debug("...received")

            if groupChatMember is None:
                LOG.error("Member not found in group: " + str(chatId))
                return False

            if groupChatMember.status is ChatMemberStatus.OWNER or groupChatMember.status is ChatMemberStatus.ADMINISTRATOR:
                return True

            return False

        except Exception as e:
            LOG.exception("Exception (in checkIfUserHasAdminRightsInGroupOrBotAdmin): " + str(e))
            return False



    async def commandResponseCheckParticipants(self, client: Client, message: Message):
        try:
            LOG.success("Response on command 'checkParticipants' from user: " + str(message.chat.username) if not None else "None")
            chatID = message.chat.id
            userID = message.from_user.id

            if message.from_user.username is None:
                raise Exception("User has no username")

            username: str = message.from_user.username

            hasAccess: bool = await self.checkIfUserHasAdminRightsInGroupOrBotAdmin(
                client=client,
                chatId=int(community_group_id),
                username=username
            )
            if not hasAccess:
                LOG.error("User has no access to this command")
                await client.send_message(chat_id=chatID,
                                          text="You do not have access to this command")
                return

            if message.reply_to_top_message_id:
                messageThreadID = message.reply_to_top_message_id
            else:
                messageThreadID = message.reply_to_message_id


            election: Election = self.database.getLastElection(contract=eden_account)
            if election is None:
                raise Exception("No election found in database")

            dummyElections: Election = self.database.getDummyElection(election=election)
            if dummyElections is None:
                raise Exception("No dummy elections found in database")

            participants: list[Participant] = self.database.getMembers(election=dummyElections)
            if participants is None:
                raise Exception("No participants found in database")

            knownUsers: list[KnownUser] = self.database.getKnownUsers(botName=telegram_bot_name)
            if knownUsers is None:
                raise Exception("No known users found in database")

            toSend: str = "Users that are **not known** to bot, but they will participate in next elections: \n"
            await client.send_message(chat_id=chatID,
                                      reply_to_message_id=messageThreadID,
                                      text=toSend)
            toSend = "```python \n"
            toSendIndex: int = 0
            for room, participant in participants:
                if participant.participationStatus == False:
                    #only participants that will participate in next elections
                    continue
                #iterate over known users
                isFound: bool = False
                for knownUser in knownUsers:
                    if participant.telegramID is None:
                        continue
                    if PARSE_TG_NAME(participant.telegramID).lower() == PARSE_TG_NAME(knownUser.userID).lower():
                        if knownUser.isKnown:
                            # if user is known, and not banned
                            isFound = True
                        break
                if isFound == False:
                    #add to send list, because user is known
                    participantToStr: str = "Telegram id: " + str(participant.telegramID)
                    participantToStr += ", AccountName: " + (
                        str(participant.accountName) if participant.accountName is not None else "")
                    toSend += participantToStr + "\n"
                    toSendIndex += 1
                    if toSendIndex > 30:
                        toSend += "\n ```"
                        isSent: bool = await client.send_message(chat_id=chatID,
                                                            reply_to_message_id=messageThreadID,
                                                            text=toSend)

                        toSend = "```python \n"
                        toSendIndex = 0
                        if isSent:
                            LOG.success("Message sent")
                        else:
                            LOG.error("Message not sent")
            if toSendIndex > 0:
                toSend += "\n ```"
                isSent: bool = await client.send_message(chat_id=chatID,
                                                    reply_to_message_id=messageThreadID,
                                                    text=toSend)
                if isSent:
                    LOG.success("Message sent")
                else:
                    LOG.error("Message not sent")

        except Exception as e:
            LOG.exception("Exception (in commandResponseCheckParticipants): " + str(e))
    """
    #next function is duplicated from communityGroup - because of circular imports
    def merge(self, communityParticipantsNFT: list[CommunityParticipant], participantsDB: list[Participant]) \
            -> list[CommunityParticipant]:
        try:
            LOG.debug("Merge community participants with participants from database to one list - to have NFT data"
                      "and telegram data in one list")
            for communityParticipantNFT in communityParticipantsNFT:
                LOG.info("Community participant: " + str(communityParticipantNFT) + " ... looking for telegramID")
                isFound: bool = False
                for participantDB in participantsDB:
                    if communityParticipantNFT.accountName == participantDB.accountName and \
                            participantDB.telegramID is not None and \
                            participantDB.telegramID != "":
                        LOG.info("Found telegramID: " + str(participantDB.telegramID))
                        communityParticipantNFT.telegramID = participantDB.telegramID
                        #creating custom member
                        #communityParticipantNFT.customMember = CustomMember(userId='-1',
                        #                                          username=communityParticipantNFT.telegramID,
                        #                                          memberStatus=MemberStatus.OTHER,
                        #                                          )
                        isFound = True
                        break

                if isFound is False:
                    #not found telegramID
                    communityParticipantNFT.telegramID = "-1"
                    #communityParticipantNFT.customMember = CustomMember(userId='-1',
                    #                                                    memberStatus=MemberStatus.OTHER,
                    #                                                    isUnknown=True)
            return communityParticipantsNFT
        except Exception as e:
            LOG.exception("Error in merge: " + str(e))
            raise CommunicationException("Error in merge: " + str(e))
    """
    # next function is duplicated from communityGroup - because of circular imports
    def getUsersFromDatabase(self, contractAccount: str, executionTime: datetime, rangeInMonths: int):
        assert isinstance(contractAccount, str), "contractAccount must be type of str"
        assert isinstance(executionTime, datetime), "executionTime must be type of datetime"
        assert isinstance(rangeInMonths, int), "rangeInMonths must be type of int"
        try:
            LOG.debug(
                "Get users from database with execution time " + str(executionTime - timedelta(days=rangeInMonths)))
            # desc order by account name(1) and election date(2)
            participants: list[Participant] = self.database.getParticipantByContract(contractAccount=contractAccount,
                                                                                     fromDate=executionTime - timedelta(
                                                                                         days=rangeInMonths))
            if participants is None:
                raise CommunicationException(
                    "Communication. There was an error when getting participants from database")
            return participants

        except Exception as e:
            LOG.exception("Error in getUsersFromDatabase: " + str(e))
            raise CommunicationException("Error in getUsersFromDatabase: " + str(e))

    def merge(self, communityParticipantsNFT: list[CommunityParticipant], participantsDB: list[Participant],
              participantsInGroup: list[CustomMember]) \
            -> list[CommunityParticipant]:
        assert isinstance(communityParticipantsNFT, list), "communityParticipantsNFT must be type of list"
        assert isinstance(participantsDB, list), "participantsDB must be type of list"
        assert isinstance(participantsInGroup, list), "participantsInGroup must be type of list"
        try:
            LOG.debug("Merge community participants with participants from database to one list - to have NFT data"
                      "and telegram data in one list")
            for communityParticipantNFT in communityParticipantsNFT:
                LOG.info("Community participant: " + str(communityParticipantNFT) + " ... looking for telegramID")
                isFound: bool = False
                for participantDB in participantsDB:
                    if communityParticipantNFT.accountName == participantDB.accountName and \
                            participantDB.telegramID is not None and \
                            participantDB.telegramID != "":
                        LOG.info("Found telegramID: " + str(participantDB.telegramID))
                        communityParticipantNFT.telegramID = participantDB.telegramID
                        isFound = True
                        break

                if isFound is False:
                    #not found telegramID
                    communityParticipantNFT.telegramID = "-1"

            LOG.debug("Merge community participants with participants from group to one list is completed - "
                      "to have NFT data and telegram data in one list. Now we will check which participants are not"
                      "in group and add them to list")

            inGroup: list[CommunityParticipant] = []
            for communityParticipantNFT in communityParticipantsNFT:
                assert isinstance(communityParticipantNFT, CommunityParticipant), \
                "communityParticipantNFT must be type of CommunityParticipant"

                if communityParticipantNFT.telegramID == "-1" or communityParticipantNFT.telegramID == "":
                    LOG.trace("Participant " + str(communityParticipantNFT) + " has unknown telegramID")
                    continue

                found: list[Participant] = [x for x in participantsInGroup if
                                            REMOVE_AT_SIGN_IF_EXISTS(communityParticipantNFT.telegramID.lower()) ==
                                            x.username]

                if found is not None and len(found) > 0:
                    LOG.debug("Participant " + str(found) + " is in group")
                    continue
                else:
                    LOG.debug("Participant " + str(communityParticipantNFT) + " is in the group")
                    inGroup.append(communityParticipantNFT)


            LOG.debug("Merge community participants with participants from group to one list is completed - Size: " + \
                        str(len(inGroup)))
            return inGroup
        except Exception as e:
            LOG.exception("Error in merge: " + str(e))
            raise CommunicationException("Error in merge: " + str(e))


    # next function is duplicated from communityGroup - because of circular imports
    async def getUsersWithNFTAndNotInGroup(self, contractAccount: str, executionTime: datetime, rangeInDays: int,
                                     client: Client, chatId: (str,int) ) -> \
            list[CommunityParticipant]:
        assert isinstance(contractAccount, str), "contractAccount must be type of str"
        assert isinstance(executionTime, datetime), "executionTime must be type of datetime"
        assert isinstance(rangeInDays, int), "endDate must be type of int"
        assert isinstance(client, Client), "client must be type of Client"
        assert isinstance(chatId, (str, int)), "chatId must be type of str or int"
        try:
            if rangeInDays < 0:
                raise CommunicationException("rangeInDays must be positive")
            LOG.info("Get users with NFT with execution time " + str(executionTime)
                     + " and date range" + str(rangeInDays))

            endDate: datetime = executionTime.replace(microsecond=0)
            startDate: datetime = endDate - timedelta(days=rangeInDays)

            LOG.debug("Get NFT between " + str(startDate) + " and " + str(endDate))

            givenSBT: Response = self.edenData.getGivenSBT(contractAccount=contractAccount,
                                                           startTime=startDate,
                                                           endTime=endDate)
            if isinstance(givenSBT, ResponseError):
                raise CommunicationException("There was an error when getting given SBT: " + str(givenSBT.error))

            communityParticipants: list[CommunityParticipant] = self.edenData.SBTParser(sbtReport=givenSBT.data)
            #community pactitipants has only SBT data from now

            if communityParticipants is None:
                raise CommunicationException("There was an error when parsing given SBT: " + str(givenSBT.error))
            LOG.debug(
                "Community participants has been parsed. Number of participants: " + str(len(communityParticipants)))

            # get the participants from the database
            participants: list[Participant] = self.getUsersFromDatabase(contractAccount=contractAccount,
                                                                        executionTime=executionTime,
                                                                        rangeInMonths=round(rangeInDays * 1.5 / 30))

            #get current participants in the community group
            participantsInGroup: list[CustomMember] = await self.getMembersInGroupS(client=client,
                                                                                    chatId=int(chatId))
            if len(participantsInGroup) == 0:
                LOG.exception("There was an error when getting participants from the group or group is just empty")
                raise CommunicationException("There was an error when getting participants from the group or group"
                                             "is just empty")

            # merge the participants from the database with the community participants - not known participants from
            # the database will have telegramID = -1
            communityParticipants: list[CommunityParticipant] = self.merge(communityParticipantsNFT=communityParticipants,
                                                                           participantsDB=participants,
                                                                           participantsInGroup=participantsInGroup)
            # remove duplicates
            for foundP in communityParticipants:
                foundParticipant: list[CommunityParticipant] = [x for x in communityParticipants
                                                                if x.accountName == foundP.accountName]
                if len(foundParticipant) > 1:
                    LOG.debug("Removing duplicate " + foundP.accountName + " from found list")
                    communityParticipants.remove(foundP)

            return communityParticipants
        except Exception as e:
            LOG.exception("Error in getUsersWithNFTAndNotInGroup: " + str(e))
            raise CommunicationException("Error in getUsersWithNFTAndNotInGroup: " + str(e))


    async def commandResponseCheckParticipantsSBT(self, client: Client, message: Message):
        try:
            LOG.debug("Response on command 'checkParticipantsSBT' from user: " + str(message.chat.username) if not None else "None")
            chatID = message.chat.id
            userID = message.from_user.id

            if message.from_user.username is None:
                raise Exception("User has no username")

            username: str = message.from_user.username

            hasAccess: bool = await self.checkIfUserHasAdminRightsInGroupOrBotAdmin(
                client=client,
                chatId=int(community_group_id),
                username=username
            )
            if not hasAccess:
                LOG.debug("User has no access to this command")
                LOG.error("User has no access to this command")
                await client.send_message(chat_id=chatID,
                                          text="You do not have access to this command")
                return

            if message.reply_to_top_message_id:
                messageThreadID = message.reply_to_top_message_id
            else:
                messageThreadID = message.reply_to_message_id

            RANGE_IN_DAYS = 31 * 9
            executionTime = datetime.now() - timedelta(hours=6)
            participantsGoalState: list[CommunityParticipant] = \
                await self.getUsersWithNFTAndNotInGroup(contractAccount=eden_account,
                                                 rangeInDays=RANGE_IN_DAYS,
                                                 executionTime=executionTime,
                                                 client=client,
                                                 chatId=community_group_id,
                                                 )
            if participantsGoalState is None:
                raise Exception("There was an error when getting participants with NFT")

            toSend: str = "Users that should be (but not yet) in community group (they have SBT), :\n"

            await client.send_message(chat_id=chatID,
                                reply_to_message_id=messageThreadID,
                                text=toSend)

            toSend = "```python \n"
            toSendIndex: int = 0
            for participant in participantsGoalState:
                #add to send list, because user is known
                participantToStr: str = "Telegram id: " + str(participant.telegramID)
                participantToStr += ", AccountName: " + (
                    str(participant.accountName) if participant.accountName is not None else "")
                toSend += participantToStr + "\n"
                toSendIndex += 1
                if toSendIndex > 9:
                    toSend += "\n ```"
                    await client.send_message(chat_id=chatID,
                                              reply_to_message_id=messageThreadID,
                                              text=toSend)
                    toSend = "```python \n"
                    toSendIndex = 0
            if toSendIndex > 0:
                toSend += "\n ```"
                isSent: bool = await client.send_message(chat_id=chatID,
                                                         reply_to_message_id=messageThreadID,
                                                         text=toSend)
                if isSent:
                    LOG.success("Message sent")
                else:
                    LOG.error("Message not sent")

        except Exception as e:
            LOG.exception("Exception (in commandResponseCheckParticipants): " + str(e))

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

def main():
    ###########################################
    # multiprocessing
    kva = 9
    #############################################


if __name__ == "__main__":
    main()
