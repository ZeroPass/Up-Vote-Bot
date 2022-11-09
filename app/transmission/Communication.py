import asyncio
from enum import Enum

from pyrogram.errors import FloodWait
from pyrogram.handlers import MessageHandler
from pyrogram.types import Chat, InlineKeyboardMarkup, ChatPrivileges

from app.constants.parameters import *
from app.database import Database
from app.database.participant import Participant
from app.log.log import Log

from multiprocessing import Process

from pyrogram import Client, emoji, filters, types, idle

import time


# api_id = 48490
# api_hash = "507315c8796f15903299b47730838c77"

# , /*bot_token="5512475717:AAGp0a451eha7X00wVJ4csCC0Mh_U1J1nxk"
# async def main():
#    async with Client("bot1", api_id, api_hash) as app:
#        await app.send_message("me", "Greetings from **Pyrogram**!")

class SessionType(Enum):
    USER = 1
    BOT = 2


class CommunicationException(Exception):
    pass


LOG = Log(className="Communication")


class Communication:
    # sessions = {}
    sessionUser: Client = None
    sessionBot: Client = None
    isInitialized: bool = False

    def __init__(self):
        LOG.info("Init communication")

    def start(self, apiId: int, apiHash: str, botToken: str):
        assert isinstance(apiId, int), "ApiId should be int"
        assert isinstance(apiHash, str), "ApiHash should be str"
        assert isinstance(botToken, str), "BotToken should be str"
        LOG.debug("Starting communication sessions..")
        try:
            LOG.debug("... user session")
            self.setSession(sessionType=SessionType.USER,
                            client=Client(name="session_user", api_id=apiId, api_hash=apiHash))
            self.startSession(sessionType=SessionType.USER)

            LOG.debug("... bot session")
            self.setSession(sessionType=SessionType.BOT,
                            client=Client(name="sessionBot", api_id=apiId, api_hash=apiHash, bot_token=botToken))

            # client: Client = self.getSession(SessionType.BOT)
            self.sessionBot.add_handler(
                MessageHandler(callback=Communication.wellcomeProcedure, filters=filters.new_chat_members))
            # self._init()
            self.startSession(sessionType=SessionType.BOT)

            self.isInitialized = True
            LOG.debug("... done!")
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise CommunicationException("Exception: " + str(e))

    def _init(self):
        @self.sessionBot.on_message(filters=filters.new_chat_members)
        def log(client, message):
            print(message)

    def isInitialized(self) -> bool:
        return self.isInitialized

    def getSession(self, sessionType: SessionType) -> Client:
        LOG.info("Get session: " + str(sessionType))
        return self.sessionBot if sessionType == SessionType.BOT else self.sessionUser

    def setSession(self, sessionType: SessionType, client: Client):
        LOG.info("Set session: " + str(sessionType))
        if sessionType == SessionType.BOT:
            self.sessionBot = client
        else:
            self.sessionUser = client

    def startSession(self, sessionType: SessionType):
        LOG.info("Start session: " + str(sessionType))
        if sessionType == SessionType.BOT:
            self.sessionBot.start()
        else:
            self.sessionUser.start()

    async def sendMessage(self, sessionType: SessionType, chatId: int, text: str,
                    replyMarkup: InlineKeyboardMarkup = None) -> bool:
        LOG.info("Send message to: " + str(chatId) + " with text: " + text)
        try:
            assert sessionType is not None, "Session should not be null"
            if sessionType == SessionType.BOT:
                response = self.sessionBot.send_message(chat_id=chatId, text=text, reply_markup=replyMarkup)
            else:
                response = self.sessionUser.send_message(chat_id=chatId, text=text, reply_markup=replyMarkup)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendMessage) Waiting time (in seconds): " + str(e.value))
            await asyncio.sleep(e.value)
            return self.sendMessage(sessionType=sessionType, chatId=chatId, text=text, replyMarkup=replyMarkup)
        except Exception as e:
            LOG.exception("Exception: " + str(e))

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

    def archiveGroup(self, chatId: int) -> bool:
        LOG.info("Archiving group: " + str(chatId))
        try:
            assert chatId is not None, "ChatId should not be null"
            self.sessionUser.archive_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in archiveGroup): " + str(e))
            return False

    def deleteGroup(self, chatId: int) -> bool:
        LOG.info("Deleting group: " + str(chatId))
        try:
            assert chatId is not None, "ChatId should not be null"
            self.sessionUser.delete_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in deleteGroup): " + str(e))
            return False

    def addChatMembers(self, chatId: int, participants: list) -> bool:
        LOG.info("Adding participants to group: " + str(chatId) + " with participants: " + str(participants))
        try:
            assert chatId is not None, "ChatId should not be null"
            assert participants is not None, "Participants should not be null"
            self.sessionUser.add_chat_members(chat_id=chatId,
                                              user_ids=participants)
            return True
        except Exception as e:
            LOG.exception("Exception (in addChatMembers): " + str(e))
            return False

    def promoteMembers(self, chatId: int, participants: list) -> bool:
        LOG.info("Promoting participants to group: " + str(chatId) + " with participants: " + str(participants))
        try:
            assert chatId is not None, "ChatId should not be null"
            assert participants is not None, "Participants should not be null"
            for participant in participants:
                try:
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
                except Exception as e:
                    LOG.exception("Exception (in promoteMembers): " + str(e))
            return True
        except Exception as e:
            LOG.exception("Exception (in promoteMembers): " + str(e))
            return False

    def setChatDescription(self, chatId: int, description: str) -> bool:
        LOG.info("Setting description to group: " + str(chatId) + " with description: " + str(description))
        try:
            assert chatId is not None, "ChatId should not be null"
            assert description is not None, "Description should not be null"
            self.sessionUser.set_chat_description(chat_id=chatId,
                                                  description=description)
            return True
        except Exception as e:
            LOG.exception("Exception (in setChatDescription): " + str(e))
            return False

    def leaveChat(self, chatId: int) -> bool:
        LOG.info("Leaving group: " + str(chatId))
        try:
            assert chatId is not None, "ChatId should not be null"
            self.sessionUser.leave_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in leaveChat): " + str(e))
            return False

    #
    # Filters management
    #

    async def wellcomeProcedure(client: Client, message):
        LOG.success("New chat member: " + str(message.new_chat_members))
        chatid = message.chat.id
        LOG.success(".. in chat: " + str(chatid))
        database: Database = Database()
        for newMember in message.new_chat_members:
            if isinstance(newMember, types.User):
                LOG.success("Wellcome message to user: " + str(newMember.id))
                LOG.debug("... with username: " + str(newMember.username) if newMember.username is not None else "None")
                LOG.debug("...name: " + str(newMember.first_name) if newMember.first_name is not None else "None")
                LOG.debug("...last name: " + str(newMember.last_name) if newMember.last_name is not None else "None")
                await client.send_message(chatid, "Wellcome " +
                                                  str(newMember.username) if newMember.username is not None else "" +
                                                                                                                 " to the chat!")

                # promote only users who supposed to be in this room
                participants: list[Participant] = database.getUsersInRoom(roomTelegramID=chatid)
                for participant in participants:
                    if participant.telegramID is not None and participant.telegramID == newMember.username:
                        LOG.debug("User supposed to be in this room: " + str(participant.telegramID) + " - promoting!")
                        await client.promote_chat_member(chat_id=chatid,
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
                        LOG.success("Promoting  user " + str(participant.telegramID) + " to admin successfully done!")
                        break
                return
            else:
                LOG.success("New member is not instance of 'User'")

    def idle(self):
        idle()

    def setFilters(self):
        LOG.info("Set filters: " + str(filters))
        client: Client = self.getSession(SessionType.BOT)
        # client1: Client = self.getSession(SessionType.USER)

        client.add_handler(MessageHandler(callback=Communication.wellcomeProcedure))  # """, filters=filters.text"""
        # client.run()

        idle()

        ######

        async def welcome(bot, message):
            LOG.success("New chat member: " + str(message.new_chat_members))
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))
            await bot.send_message(text=f"Welcome {message.from_user.mention} to {message.chat.username}",
                                   chat_id=chatid)
            database: Database = Database()

            # promote only users who supposed to be in this room
            participants: list[Participant] = database.getUsersInRoom(roomTelegramID=chatid)
            for participant in participants:
                if participant.telegramID is not None and \
                        participant.telegramID == message.chat.username:
                    LOG.debug("User supposed to be in this room: " + str(participant.telegramID) + " - promoting!")
                    bot.promoteMembers(chatId=chatid, participants=[message.chat.username])


def runPyrogram():
    comm = Communication()
    comm.start(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    # chatID = comm.createSuperGroup(name="test1", description="test1")
    chatID = -1
    botID = 1
    botName = '1'
    userID = 1
    # first intecation
    comm.sendMessage(sessionType=SessionType.USER, chatId=botName, text="From bot")

    print("chatID: " + str(chatID))
    print(chatID)
    print("------")
    comm.addChatMembers(chatId=chatID, participants=["1", botName])
    comm.promoteMembers(chatId=chatID, participants=[botName])
    comm.sendMessage(sessionType=SessionType.USER, chatId=chatID, text="Hello world!564565464")
    comm.idle()


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
