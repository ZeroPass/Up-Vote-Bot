import re
import time
from datetime import datetime, timedelta
from itertools import groupby

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from chain.dfuse import Response, ResponseSuccessful, ResponseError
from chain.stateElectionState import ElectCurrTable
from constants import telegram_bot_name, telegram_admins_id
from database.participant import Participant
from log import Log

from chain import EdenData
from text.textManagement import CommunityGroupManagement, Button
from transmission import Communication, SessionType
from database import Database
from database.comunityParticipant import CommunityParticipant
from community import CommunityList, CommunityListState
from debugMode.modeDemo import ModeDemo
from transmissionCustom import REMOVE_AT_SIGN_IF_EXISTS, CustomMember, AdminRights, MemberStatus

LOG = Log(className="CommunityGroup")


class CommunityGroupException(Exception):
    pass

CUSTOM_TAG_CHIEF_DELEGATE = "Chief Delegate"
CUSTOM_TAG_DELEGATE = "L{} Delegate"
CUSTOM_TAG_REGULAR_EXPRESSION = r"^(Chief Delegate|L.*Delegate)$"

class CommunityGroup:
    def __init__(self, edenData: EdenData, database: Database, communication: Communication, mode: ModeDemo,
                 testing: bool = False):
        assert isinstance(edenData, EdenData), "edenData must be an EdenData object"
        assert isinstance(database, Database), "database must be a Database object"
        assert isinstance(communication, Communication), "communication must be a Communication object"
        assert isinstance(mode, ModeDemo), "mode must be a ModeDemo object"
        assert isinstance(testing, bool), "testing must be a bool"

        self.edenData = edenData
        self.database = database
        self.communication = communication
        self.mode = mode
        self.testing = testing

    # def givenSBTParser(self):

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
                raise CommunityGroupException(
                    "CommunityGroup. There was an error when getting participants from database")
            return participants

        except Exception as e:
            LOG.exception("Error in getUsersFromDatabase: " + str(e))
            raise CommunityGroupException("Error in getUsersFromDatabase: " + str(e))

    def setTag(self, level: int = None, isFinal: bool = False):
        assert isinstance(level, (int, type(None))), "level must be type of int or None"
        assert isinstance(isFinal, bool), "isFinal must be type of bool"
        try:
            if level is None and isFinal is False:
                raise CommunityGroupException("level and isFinal cannot be None at the same time")

            if isFinal:
                return CUSTOM_TAG_CHIEF_DELEGATE
            else:
                if level < 0:
                    raise CommunityGroupException("level must be positive")
                return CUSTOM_TAG_DELEGATE.format(level)
        except Exception as e:
            LOG.exception("Error in setTag: " + str(e))
            raise CommunityGroupException("Error in setTag: " + str(e))

    def checkIfPredefinedTag(tag: str) -> bool:
        assert isinstance(tag, str), "tag must be type of str"
        try:
            if re.search(CUSTOM_TAG_REGULAR_EXPRESSION, tag):
                return True
            else:
                return False
        except Exception as e:
            LOG.exception("Error in checkIfPredefinedTag: " + str(e))
            raise CommunityGroupException("Error in checkIfPredefinedTag: " + str(e))


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
                        isFound = True
                        break

                if isFound is False:
                    #not found telegramID
                    communityParticipantNFT.telegramID = "-1"
            return communityParticipantsNFT
        except Exception as e:
            LOG.exception("Error in merge: " + str(e))
            raise CommunityGroupException("Error in merge: " + str(e))

    def mergeActionInducted(self, accounts: list[str], participantsDB: list[Participant]) \
            -> list[Participant]:
        try:
            LOG.debug("Merge accounts(EOS) with participants from database to one list - to have NFT data"
                      "and telegram data in one list")

            toReturn: list[Participant] = []
            for account in accounts:
                LOG.info("Account: " + str(account) + " ... looking for telegramID")
                for participantDB in participantsDB:
                    if account == participantDB.accountName and \
                            participantDB.telegramID is not None and \
                            participantDB.telegramID != "":
                        toReturn.append(Participant.deepCopy(participantDB))
                        break
            return toReturn
        except Exception as e:
            LOG.exception("Error in merge: " + str(e))
            raise CommunityGroupException("Error in merge: " + str(e))

    def getUsersWithNFT(self, contractAccount: str, executionTime: datetime, rangeInDays: int) -> \
            list[CommunityParticipant]:
        assert isinstance(contractAccount, str), "contractAccount must be type of str"
        assert isinstance(executionTime, datetime), "executionTime must be type of datetime"
        assert isinstance(rangeInDays, int), "endDate must be type of int"
        try:
            if rangeInDays < 0:
                raise CommunityGroupException("rangeInDays must be positive")
            LOG.info("Get users with NFT with execution time " + str(executionTime)
                     + " and date range" + str(rangeInDays))

            endDate: datetime = executionTime.replace(microsecond=0)
            startDate: datetime = endDate - timedelta(days=rangeInDays)

            LOG.debug("Get NFT between " + str(startDate) + " and " + str(endDate))

            givenSBT: Response = self.edenData.getGivenSBT(contractAccount=contractAccount,
                                                           startTime=startDate,
                                                           endTime=endDate)
            if isinstance(givenSBT, ResponseError):
                raise CommunityGroupException("There was an error when getting given SBT: " + str(givenSBT.error))

            communityParticipants: list[CommunityParticipant] = self.edenData.SBTParser(sbtReport=givenSBT.data)
            #community pactitipants has only SBT data from now

            if communityParticipants is None:
                raise CommunityGroupException("There was an error when parsing given SBT: " + str(givenSBT.error))
            LOG.debug(
                "Community participants have been parsed. Number of participants: " + str(len(communityParticipants)))

            # get the participants from the database
            participants: list[Participant] = self.getUsersFromDatabase(contractAccount=contractAccount,
                                                                        executionTime=executionTime,
                                                                        rangeInMonths=round(rangeInDays * 1.5 / 30))
            # merge the participants from the database with the community participants - not known participants from
            # the database will have telegramID = -1
            communityParticipants = self.merge(communityParticipantsNFT=communityParticipants, participantsDB=participants)
            return communityParticipants
        except Exception as e:
            LOG.exception("Error in getUsersWithNFT: " + str(e))
            raise CommunityGroupException("Error in getUsersWithNFT: " + str(e))

    def getActionInducted(self,
                          contractAccount: str,
                          executionTime: datetime,
                          rangeInDays: int) -> \
            list[Participant]:
        assert isinstance(contractAccount, str), "contractAccount must be type of str"
        assert isinstance(executionTime, datetime), "executionTime must be type of datetime"
        assert isinstance(rangeInDays, int), "endDate must be type of int"
        try:
            if rangeInDays < 0:
                raise CommunityGroupException("rangeInDays must be positive")
            LOG.info("Get users with action inductee was called; execution time " + str(executionTime)
                     + " and date range" + str(rangeInDays))

            endDate: datetime = executionTime.replace(microsecond=0)
            startDate: datetime = endDate - timedelta(days=rangeInDays)

            LOG.debug("Get actions between " + str(startDate) + " and " + str(endDate))

            inductedActions: Response = self.edenData.getActionsInducted(contractAccount=contractAccount,
                                                                  startTime=startDate,
                                                                  endTime=endDate)
            if isinstance(inductedActions, ResponseError):
                raise CommunityGroupException("There was an error when getting actions: " + str(inductedActions.error))

            #get accounts(eos) from indcuted actions in range
            accounts: list[str] = self.edenData.actionInductedParser(report=inductedActions.data)

            if accounts is None:
                raise CommunityGroupException("There was an error when parsing inducted actions: "
                                              + str(inductedActions.error))
            LOG.debug("Accounts have been parsed. Number of participants: " + str(len(accounts)))

            participants: list[Participant] = self.getUsersFromDatabase(contractAccount=contractAccount,
                                                                        executionTime=executionTime,
                                                                        rangeInMonths=round(rangeInDays * 4.5 / 30))
            # merge inducted accounts with participants from database - only matched account will be in list
            inductedParticipants: list[Participant] = self.mergeActionInducted(accounts=accounts,
                                               participantsDB=participants)
            if inductedParticipants is None:
                raise CommunityGroupException("There was an error when merging inducted accounts with participants "
                                              "from database")

            return inductedParticipants
        except Exception as e:
            LOG.exception("Error in getActionInducted: " + str(e))
            raise CommunityGroupException("Error in getActionInducted: " + str(e))

    def addGroupToKnownUsersAndCheckAdminRight(self, communityGroupID: int):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        try:
            LOG.debug("Add community group to known users table (of current bot)")
            response: bool = self.communication.knownUserData.setKnownUser(botName=telegram_bot_name,
                                                                           telegramID=communityGroupID,
                                                                           isKnown=True)
            if response:
                LOG.success("Community group has been added to known users table")
            else:
                LOG.exception("Community group has not been added to known users table")
                raise CommunityGroupException("Community group has not been added to known users table")

            LOG.debug("Check if bot has admin rights in community group")
            bot: CustomMember = self.communication.getMemberInGroup(sessionType=SessionType.BOT,
                                                chatId=communityGroupID,
                                                userId=telegram_bot_name)

            if bot is None:
                LOG.exception("Bot is not in community group")
                raise CommunityGroupException("Bot is not in community group")
            if bot.adminRights.isAdmin is False:
                LOG.exception("Bot is not admin in community group")
                raise CommunityGroupException("Bot is not admin in community group")

            if bot.adminRights.canPromoteMembers is False:
                LOG.exception("Bot has not admin rights to promote members in community group")
                raise CommunityGroupException("Bot has not admin rights to promote members in community group")

            if bot.adminRights.canRestrictMembers is False:
                LOG.exception("Bot has not admin rights to restrict members in community group")
                raise CommunityGroupException("Bot has not admin rights to restrict members in community group")
            if bot.adminRights.canInviteUsers is False:
                LOG.exception("Bot has not admin rights to invite users in community group")
                raise CommunityGroupException("Bot has not admin rights to invite users in community group")
            LOG.success("Bot is admin in community group.")

        except Exception as e:
            LOG.exception("Error in addGroupToKnownUsers: " + str(e))
            raise CommunityGroupException("Error in addGroupToKnownUsers: " + str(e))


    def fromCustomMembersToCommunityParticipants(self, customMembers: list[CustomMember],
                                                     contractAccount: str,
                                                     executionTime: datetime,
                                                     rangeInDays: int) -> CommunityParticipant:
        assert isinstance(customMembers, list), "customMembers must be type of list"
        try:
            LOG.debug("Convert list of CustomMembers to list of CommunityParticipants")

            participantsDB: list[Participant] = self.getUsersFromDatabase(contractAccount=contractAccount,
                                                                        executionTime=executionTime,
                                                                        rangeInMonths=round(rangeInDays * 1.5 / 30))

            toReturn: list[CommunityParticipant] = []

            if participantsDB is None:
                raise CommunityGroupException("List of participants from DB is empty. Can not do anything.")

            for customMember in customMembers:
                assert isinstance(customMember, CustomMember), "customMember must be type of CustomMember"

                if customMember.username is None:
                    LOG.error("Custom member.username is None. User did not set username in telegram!")
                    #unknown user - set isUnknown to True to delete it later
                    customMember.isUnknown = True
                    toReturn.append(CommunityParticipant.justCustomMember(customMember=customMember))
                    continue

                found: list[Participant] = [x for x in participantsDB if REMOVE_AT_SIGN_IF_EXISTS(x.telegramID.lower()) ==
                                                                                 customMember.username]

                if found is not None and len(found) > 0:
                    foundParticipant: Participant = found[0]
                    foundParticipant.telegramID = customMember.username
                    toReturn.append(CommunityParticipant.fromParticipant(participant=foundParticipant,
                                                                         customMember=customMember))
                else:
                    # unknown user - set isUnknown to True to delete it later from community group
                    customMember.isUnknown = True
                    cp: CommunityParticipant = CommunityParticipant.justCustomMember(customMember=customMember)
                    cp.telegramID = customMember.username
                    toReturn.append(cp)

            LOG.debug("Number of community participants: " + str(len(toReturn)))
            return toReturn
        except Exception as e:
            LOG.exception("Error in fromCustomMemberToCommunityParticipant: " + str(e))
            raise CommunityGroupException("Error in fromCustomMemberToCommunityParticipant: " + str(e))

    def getUsersFromCommunityGroup(self, communityGroupID: int) -> list[CustomMember]:
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        try:
            LOG.debug("Get users from community group")
            customMembers: list[CustomMember] = self.communication.getMembersInGroup(sessionType=SessionType.BOT,
                                                                                     chatId=communityGroupID)
            if customMembers is None or len(customMembers) == 0:
                LOG.exception("There was an error when getting users from community group")
                raise CommunityGroupException("There was an error when getting users from community group")
            return customMembers

        except Exception as e:
            LOG.exception("Error in getUsersFromCommunityGroup: " + str(e))
            return None


    def reportToAdmin(self, adminTelegram: str, participants: list[CommunityParticipant], add: bool):
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        assert isinstance(participants, list), "participants must be type of list"
        assert isinstance(add, bool), "add must be type of bool"
        try:
            LOG.debug("Start process of sending users (to admin) that needs to be removed/added")
            text:str = "addded in" if add else "removed from"

            toSend: str = "Users that will be " + text + " community group:\n"
            self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatId=adminTelegram,
                                           text=toSend)
            toSend = "```python"
            counter: int = 0
            for participant in participants:

                participantToStr: str = "Telegram id: @" + str(participant.telegramID)
                participantToStr += ", AccountName: " + (str(participant.accountName) if participant.accountName is not None else "")
                toSend += participantToStr + "\n"
                counter += 1
                if counter == 30:
                    toSend += "\n ```"
                    isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                               chatId=adminTelegram,
                                               text=toSend)
                    toSend = "```python"
                    counter = 0
                    if isSent:
                        LOG.success("Message sent")
                    else:
                        LOG.error("Message not sent")
            if toSend != "```python":
                toSend += "\n ```"
                isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                             chatId=adminTelegram,
                                                             text=toSend)
                if isSent:
                    LOG.success("Message sent")
                else:
                    LOG.error("Message not sent")
        except Exception as e:
            LOG.exception("Error in reportToAdmin: " + str(e))
            raise CommunityGroupException("Error in reportToAdmin : " + str(e))


    def reportToAdminAboutAdmin(self, adminTelegram: str, participants: list[CommunityParticipant], add: bool):
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        assert isinstance(participants, list), "participants must be type of list"
        assert isinstance(add, bool), "add must be type of bool"
        try:
            LOG.debug("Start process of sending users (to admin) that needs to be removed/added from admin group")
            text: str = "addded to" if add else "removed from"

            toSend: str = "Users that will be " + text + " group of admins:\n"
            self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatId=adminTelegram,
                                           text=toSend)
            toSend = "```python"
            counter: int = 0
            for participant in participants:

                participantToStr: str = "\n Telegram id: " + str(participant.telegramID)
                participantToStr += ", AccountName: " + (str(participant.accountName) if participant.accountName is not None else "")
                participantToStr += ", Custom member: " + (str(participant.customMember) if participant.customMember is not None else "")
                toSend += participantToStr + "\n"
                counter += 1
                if counter == 20:
                    toSend += "\n ```"
                    isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                               chatId=adminTelegram,
                                               text=toSend)
                    toSend = "```python"
                    counter = 0
                    if isSent:
                        LOG.success("Message sent")
                    else:
                        LOG.error("Message not sent")
            if toSend != "```python":
                toSend += "\n ```"
                isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                             chatId=adminTelegram,
                                                             text=toSend)
                if isSent:
                    LOG.success("Message sent")
                else:
                    LOG.error("Message not sent")
        except Exception as e:
            LOG.exception("Error in reportToAdminAboutAdmin: " + str(e))
            raise CommunityGroupException("Error in reportToAdminAboutAdmin : " + str(e))

    def reportToAdminAboutTags(self, adminTelegram: str, participants: list[CommunityParticipant]):
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        assert isinstance(participants, list), "participants must be type of list"
        try:
            LOG.debug("Start process of sending users (to admin) that needs to use new tags")

            toSend: str = "Users that need new tag:\n"
            self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatId=adminTelegram,
                                           text=toSend)
            toSend = "```python"
            counter: int = 0
            for participant in participants:
                if participant.customMember is None:
                    continue
                participantToStr: str = "Telegram id: " + str(participant.telegramID)
                participantToStr += ", AccountName: " + (str(participant.accountName) if participant.accountName is not None else "")
                participantToStr += ", Custom member tag: " + (str(participant.customMember.tag) if participant.customMember.tag is not None else "")
                toSend += participantToStr + "\n"
                counter += 1
                if counter == 20:
                    toSend += "\n ```"
                    isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                               chatId=adminTelegram,
                                               text=toSend)
                    toSend = "```python"
                    counter = 0
                    if isSent:
                        LOG.success("Message sent")
                    else:
                        LOG.error("Message not sent")
            if toSend != "```python":
                toSend += "\n ```"
                isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                             chatId=adminTelegram,
                                                             text=toSend)
                if isSent:
                    LOG.success("Message sent")
                else:
                    LOG.error("Message not sent")
        except Exception as e:
            LOG.exception("Error in reportToAdminAboutAdmin: " + str(e))
            raise CommunityGroupException("Error in reportToAdminAboutAdmin : " + str(e))

    def removeUsers(self, communityGroupID: int, communityList: CommunityList, adminTelegram: str):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(communityList, CommunityList), "communityList must be type of CommunityList"
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        try:
            LOG.debug("Start removing users from community group")
            toRemove: list[CommunityParticipant] = communityList.usersThatAreInGroupButShouldNotBe()

            if toRemove is None:
                LOG.exception("removeUsers; toRemove is None")
                return

            LOG.debug("Number of users to remove: " + str(len(toRemove)))

            self.reportToAdmin(adminTelegram=adminTelegram,
                               participants=toRemove,
                               add=False)



            for communityParticipant in toRemove:
                try:
                    assert isinstance(communityParticipant, CommunityParticipant), \
                        "communityParticipant must be type of CommunityParticipant"
                    if communityParticipant.telegramID == "":
                        LOG.debug("User has no telegramID. Skip removing him from community group")
                        continue

                    if self.testing:
                        LOG.debug("account " + str(communityParticipant.accountName) + ", tg " + communityParticipant.telegramID)
                        #LOG.debug("User to remove: " + str(communityParticipant.accountName) + ", tg:" +communityParticipant.telegramID)
                    else:
                        response: bool = self.communication.removeUserFromGroup(sessionType=SessionType.BOT,
                                                                                chatId=communityGroupID,
                                                                                userId=communityParticipant.telegramID)
                        if response:
                            LOG.success("User has been removed from community group")
                        else:
                            LOG.exception("User has not been removed from community group")
                            raise CommunityGroupException("User has not been removed from community group")
                except Exception as e:
                    LOG.exception("Error in removeUsers(inline loop): " + str(e))
                    #raise CommunityGroupException("Error in removeUsers(inline loop): " + str(e))
            LOG.success("Users without SBT token has been removed successfully")
        except Exception as e:
            LOG.exception("Error in removeUsers: " + str(e))
            raise CommunityGroupException("Error in removeUsers: " + str(e))

    def sendInvitationLink(self, communityGroupID: int, communityList: CommunityList, adminTelegram: str):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(communityList, CommunityList), "communityList must be type of CommunityList"
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        try:
            LOG.debug("Start adding users to community group")
            toRemove: list[CommunityParticipant] = communityList.usersThatAreNotInGroupButShouldBe()

            if toRemove is None:
                LOG.exception("sendInvitationLink; toRemove is None")
                return

            LOG.debug("Number of users to add: " + str(len(toRemove)))

            self.reportToAdmin(adminTelegram=adminTelegram,
                               participants=toRemove,
                               add=True)

            cgm: CommunityGroupManagement = CommunityGroupManagement()

            inviteLink: str = self.communication.getGeneralChatLink(sessionType=SessionType.BOT, chatId=communityGroupID)
            if inviteLink is None:
                LOG.exception("addUsersOrSendInvitationLink; Error when getting invite link")
                raise CommunityGroupException("addUsersOrSendInvitationLink; Error when getting invite link")


            for communityParticipant in toRemove:
                try:
                    assert isinstance(communityParticipant, CommunityParticipant), \
                        "communityParticipant must be type of CommunityParticipant"
                    if communityParticipant.telegramID == "":
                        LOG.debug("User has no telegramID. Skip removing him from community group")
                        continue


                    if self.testing:
                        LOG.debug("account " + str(communityParticipant.accountName) + ", tg " + communityParticipant.telegramID)
                    else:

                        button: Button = cgm.invitationToGroupButton(inviteLink=inviteLink)
                        text: str = cgm.invitationToGroup()
                        response: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                       chatId=communityParticipant.telegramID,
                                                       text=text,
                                                       inlineReplyMarkup=InlineKeyboardMarkup(
                                                           inline_keyboard=
                                                           [
                                                               [
                                                                   InlineKeyboardButton(text=button[0]['text'],
                                                                                        url=button[0]['value']),

                                                               ]
                                                           ]
                                                       ))
                        LOG.debug("Sending invitation link to user: " + str(communityParticipant.telegramID) +
                                  " was successful: " + "true" if response else "false")
                except Exception as e:
                    LOG.exception("Error in addUsersOrSendInvitationLink(inline loop): " + str(e))
                    #raise CommunityGroupException("Error in addUsersOrSendInvitationLink(inline loop): " + str(e))
        except Exception as e:
            LOG.exception("Error in addUsersOrSendInvitationLink: " + str(e))
            raise CommunityGroupException("Error in addUsersOrSendInvitationLink: " + str(e))

    def removeUsersFromAdminGroup(self, communityGroupID: int, communityList: CommunityList, adminTelegram: str):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(communityList, CommunityList), "communityList must be type of CommunityList"
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        try:
            LOG.debug("Start removing users from admin group")
            toRemove: list[CommunityParticipant] = \
                communityList.usersThatAreAdminsButShouldNotBe()

            if toRemove is None:
                LOG.exception("removeUsersFromAdminGroup; toRemove is None")
                return

            LOG.debug("Number of users to remove: " + str(len(toRemove)))
            self.reportToAdminAboutAdmin(adminTelegram=adminTelegram,
                                         participants=toRemove,
                                         add=False)
            for communityParticipant in toRemove:
                try:
                    assert isinstance(communityParticipant, CommunityParticipant), \
                        "communityParticipant must be type of CommunityParticipant"

                    if communityParticipant.telegramID == "":
                        LOG.debug("User has no telegramID. Skip adding him to community group")
                        continue

                    if self.testing:
                        LOG.debug("account " + str(communityParticipant.accountName) + ", tg " + communityParticipant.telegramID)


                    else:
                        response: bool = self.communication.promoteSpecificMember(sessionType=SessionType.BOT,
                                                                              userId=communityParticipant.telegramID,
                                                                              chatId=communityGroupID,
                                                                              adminRights=AdminRights(isAdmin=False))
                        if response:
                            LOG.success("User has been removed from admin group")
                        else:
                            LOG.exception("User has not been removed from admin group")
                            #raise CommunityGroupException("User has not been removed from admin group")
                except Exception as e:
                    LOG.exception("Error in removeUsersFromAdminGroup(inline loop): " + str(e))
                    #raise CommunityGroupException("Error in removeUsersFromAdminGroup(inline loop): " + str(e))
            LOG.success("Users that are no longer chief delegates or part of maintaining team has been removed from"
                        " administrator group")
        except Exception as e:
            LOG.exception("Error in removeUsersFromAdminGroup: " + str(e))
            raise CommunityGroupException("Error in removeUsersFromAdminGroup: " + str(e))

    def addUsersToAdminGroup(self, communityGroupID: int, communityList: CommunityList, adminTelegram: str):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(communityList, CommunityList), "communityList must be type of CommunityList"
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        try:
            LOG.debug("Start adding users to admin group")
            toAdd: list[CommunityParticipant] = \
                communityList.usersThatAreNotYetAdminsButShouldBe()

            if toAdd is None:
                LOG.exception("addUsersToAdminGroup; toRemove is None")
                return
            LOG.debug("Number of users to add: " + str(len(toAdd)))

            self.reportToAdminAboutAdmin(adminTelegram=adminTelegram,
                                         participants=toAdd,
                                         add=True)

            for communityParticipant in toAdd:
                try:
                    assert isinstance(communityParticipant, CommunityParticipant), \
                        "communityParticipant must be type of CommunityParticipant"

                    if communityParticipant.telegramID == "":
                        LOG.debug("User has no telegramID. Skip adding him to community group")
                        continue

                    if self.testing:
                        LOG.debug("account " + str(
                            communityParticipant.accountName) + ", tg " + communityParticipant.telegramID)

                    else:
                        if communityParticipant.customMember is None or \
                                communityParticipant.customMember.adminRights is None:
                            LOG.error("communityParticipant.customMember is None or "
                                      "communityParticipant.customMember.adminRights is None")
                            continue

                        response: bool = self.communication.\
                            promoteSpecificMember(sessionType=SessionType.BOT,
                                                                                  userId=communityParticipant.telegramID,
                                                                                  chatId=communityGroupID,
                                                                                  adminRights=AdminRights(isAdmin=True,
                                                                                      canManageChat=communityParticipant.customMember.adminRights.canManageChat,
                                                                                        canDeleteMessages=communityParticipant.customMember.adminRights.canDeleteMessages,
                                                                                        canManageVideoChats=communityParticipant.customMember.adminRights.canManageVideoChats,
                                                                                        canRestrictMembers=communityParticipant.customMember.adminRights.canRestrictMembers,
                                                                                        canPromoteMembers=communityParticipant.customMember.adminRights.canPromoteMembers,
                                                                                        canChangeInfo=communityParticipant.customMember.adminRights.canChangeInfo,
                                                                                        canPostMessages=communityParticipant.customMember.adminRights.canPostMessages,
                                                                                        canEditMessages=communityParticipant.customMember.adminRights.canEditMessages,
                                                                                        canInviteUsers=communityParticipant.customMember.adminRights.canInviteUsers,
                                                                                        canPinMessages=communityParticipant.customMember.adminRights.canPinMessages,
                                                                                        isAnonymous=communityParticipant.customMember.adminRights.isAnonymous)
                                                                                      )
                        if response:
                            LOG.success("User has been added to admin group")
                        else:
                            LOG.exception("User has not been added to admin group")
                            #raise CommunityGroupException("User has not been added to admin group")
                except Exception as e:
                    LOG.exception("Error in addUsersToAdminGroup(inline loop): " + str(e))
                    #raise CommunityGroupException("Error in addUsersToAdminGroup(inline loop): " + str(e))
            LOG.success("Users that are chief delegates or part of maintaining team has been added to administrator group")
        except Exception as e:
            LOG.exception("Error in addUsersToAdminGroup: " + str(e))
            raise CommunityGroupException("Error in addUsersToAdminGroup: " + str(e))

    def setTagsInGroup(self, communityGroupID: int, communityList: CommunityList, adminTelegram: str):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(communityList, CommunityList), "communityList must be type of CommunityList"
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        try:
            LOG.debug("Start setting tags in group")
            usersWithWrongTags: list[CommunityParticipant] = \
                communityList.usersWithWrongTags()
            if usersWithWrongTags is None:
                LOG.exception("There are no users with wrong tags")
                return

            LOG.debug("Number of users with wrong tags: " + str(len(usersWithWrongTags)))

            self.reportToAdminAboutTags(adminTelegram=adminTelegram,
                                         participants=usersWithWrongTags)

            for communityParticipant in usersWithWrongTags:
                try:
                    assert isinstance(communityParticipant, CommunityParticipant), \
                        "communityParticipant must be type of CommunityParticipant"

                    if communityParticipant.telegramID == "":
                        LOG.debug("User has no telegramID. Skip adding him to community group")
                        continue

                    if self.testing:
                        #LOG.debug("User to set tags: " + str(communityParticipant))
                        LOG.debug("account " + str(communityParticipant.accountName) +
                                  ", tg " + communityParticipant.telegramID +
                                  ", tag " + communityParticipant.customMember.tag)


                        LOG.debug("Users ready for admin group: " + str(
                            communityParticipant.accountName) + ", tg:" + communityParticipant.telegramID + ", tag: " +
                                    communityParticipant.customMember.tag)
                    else:
                        response: bool = self.communication.setAdministratorTitle(sessionType=SessionType.BOT,
                                                                    userId=communityParticipant.telegramID,
                                                                    chatId=communityGroupID,
                                                                    title=communityParticipant.customMember.tag)
                        if response:
                            LOG.success("Tags has been set for user")
                        else:
                            LOG.exception("Tags has not been set for user")
                            #raise CommunityGroupException("Tags has not been set for user")
                except Exception as e:
                    LOG.exception("Error in setTagsInGroup(inline loop): " + str(e))
                    #raise CommunityGroupException("Error in setTagsInGroup(inline loop): " + str(e))



        except Exception as e:
            LOG.exception("Error in setTagsInGroup: " + str(e))
            raise CommunityGroupException("Error in setTagsInGroup: " + str(e))

    def manipulateCommunityGroup(self, communityGroupID: int, communityList: CommunityList, adminTelegram: str):
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(communityList, CommunityList), "communityList must be type of CommunityList"
        assert isinstance(adminTelegram, str), "adminTelegram must be type of str"
        try:
            LOG.debug("Start process of managing community group.")

            LOG.debug("Start removing users from community group")
            self.removeUsers(communityGroupID=communityGroupID, communityList=communityList,
                             adminTelegram=adminTelegram)
            LOG.success("Users without SBT token has been removed successfully")

            LOG.debug("Start adding users to community group")
            self.sendInvitationLink(communityGroupID=communityGroupID, communityList=communityList,
                                    adminTelegram=adminTelegram)
            LOG.success("Process of adding users (or they got invitation)  has been successfully finished")


            LOG.debug("Start adding users to admin group")
            self.addUsersToAdminGroup(communityGroupID=communityGroupID, communityList=communityList,
                                      adminTelegram=adminTelegram)
            LOG.success("Users that are chief delegates or part of maintaining team has been added as administrator"
                        " successfully")

            LOG.debug("Set admin tags in group")
            self.setTagsInGroup(communityGroupID=communityGroupID, communityList=communityList,
                                adminTelegram=adminTelegram)
            LOG.success("Admin tags in gropu has been set successfully")

            LOG.debug("Start removing users from admin group")
            self.removeUsersFromAdminGroup(communityGroupID=communityGroupID, communityList=communityList,
                                           adminTelegram=adminTelegram)
            LOG.success("Users that are no longer chief delegates or part of maintaining team has been removed from"
                        " administrator group")

        except Exception as e:
            LOG.exception("Error in manipulateCommunityGroup: " + str(e))
            raise CommunityGroupException("Error in manipulateCommunityGroup: " + str(e))

    def gettingBoard(self, electionCurrState: ElectCurrTable):
        assert isinstance(electionCurrState, ElectCurrTable), "electionCurrState must be type of ElectCurrTable"
        try:
            LOG.debug("Start getting board")
            currentBoard: list[str] = electionCurrState.getBoard()
            if len(currentBoard) == 0:
                LOG.exception("Board is empty")
                raise CommunityGroupException("Board is empty")
            return currentBoard
        except Exception as e:
            LOG.exception("Error in gettingBoard: " + str(e))
            raise CommunityGroupException("Error in gettingBoard: " + str(e))

    def setTagAndAdminRights(self, participantsGoal: list[CommunityParticipant],
                             electionCurrState: ElectCurrTable) -> list[CommunityParticipant]:
        assert isinstance(participantsGoal, list), "participants must be type of list"
        assert isinstance(electionCurrState, ElectCurrTable), "electionCurrState must be type of ElectCurrTable"
        try:
            LOG.debug("Set tag and admin rights")

            LOG.success("............................")
            for goalU in participantsGoal:
                kva = goalU.customMember if goalU.customMember is not None else "None"
                LOG.success("AN: " + str(goalU.accountName) + " customUser: " + str(kva))

            def truncateToNearestWeek(date):
                # Here, week starts on Monday
                return (date - timedelta(days=date.weekday())).date()

            participantsGoal.sort(key=lambda participant: truncateToNearestWeek(participant.sbt.received))

            groupedByDate = {
                k: list(v) for k, v in groupby(participantsGoal, key=lambda participant: truncateToNearestWeek(participant.sbt.received))
            }

            latestElectionDate, participants = list(groupedByDate.items())[-1]

            maxRound: int = 0
            for participant in participants:
                if participant.sbt.round > maxRound:
                    maxRound = participant.sbt.round
            LOG.debug("Highest level of last election is: " + str(maxRound))

            higestLevelAdminRights: AdminRights = AdminRights(isAdmin=True,
                                                              canManageChat=True,
                                                              canDeleteMessages=False,
                                                              canManageVideoChats=True,
                                                              canRestrictMembers=False,
                                                              canPromoteMembers=False,
                                                              canChangeInfo=False,
                                                              canInviteUsers=True,
                                                              canPinMessages=True,
                                                              isAnonymous=False)

            cdAdminRights: AdminRights = AdminRights(isAdmin=True,
                                                     canManageChat=True,
                                                     canDeleteMessages=True,
                                                     canManageVideoChats=True,
                                                     canRestrictMembers=True,
                                                     canPromoteMembers=True,
                                                     canChangeInfo=True,
                                                     canInviteUsers=True,
                                                     canPinMessages=True,
                                                     isAnonymous=False)

            LOG.success("Getting current CDs")
            currentBoard: list[str] = self.gettingBoard(electionCurrState=electionCurrState)

            LOG.debug("Start process of setting admin rights and tag")
            participantsWithoutDuplicates: list[CommunityParticipant] = []

            duplicates: list[CommunityParticipant] = []
            for participant in participants:
                #removing lower level participants (duplicates)
                isHighestLevel: bool = True
                for item in participants:
                    #if other is higher level anytime, delete it
                    #participant.sbt < item.sbt
                    if item.isSameAndHigherSBTround(other=participant):
                        isHighestLevel = False
                        duplicates.append(participant)
                        break
                if isHighestLevel:
                    participantsWithoutDuplicates.append(participant)

            LOG.debug("Removed: " + str(item) + "; New: " + str(participant))

            for index, participant in enumerate(participantsWithoutDuplicates):
                #current CD
                if any(participant.accountName in x for x in currentBoard):
                    LOG.success("Current CD: " + str(participant.accountName))
                    participantsWithoutDuplicates[index].customMember = \
                        CustomMember(userId="1",
                                     memberStatus=MemberStatus.ADMINISTRATOR,
                                     tag=self.setTag(isFinal=True),
                                     adminRights=cdAdminRights)

                #last round tags
                elif participant.sbt.round == maxRound:
                    LOG.success("last round: " + str(participant.accountName))
                    participantsWithoutDuplicates[index].customMember = \
                                CustomMember(userId="1",
                                             memberStatus=MemberStatus.ADMINISTRATOR,
                                             tag=self.setTag(level=participant.sbt.round),
                                             adminRights=higestLevelAdminRights)
                else:
                    participantsWithoutDuplicates[index].customMember = \
                                    CustomMember(userId="-1",
                                                 memberStatus=MemberStatus.MEMBER)

            # remove duplicates from base list
            for participant in duplicates:
                for goalParticiapnt in participantsGoal:
                    if participant.isSameWithoutCustomMember(other=goalParticiapnt):
                        participantsGoal.remove(goalParticiapnt)
                        break

            # update participantsGoal with new data
            #for participant in participantsWithoutDuplicates:
            #    for goalParticiapnt in participantsGoal:
            #        if participant.isSameWithoutCustomMember(other=goalParticiapnt):
            #            goalParticiapnt.customMember = participant.customMember
            #            break
            return participantsGoal
        except Exception as e:
            LOG.exception("Error in setTagAndAdminRights: " + str(e))
            raise CommunityGroupException("Error in setTagAndAdminRights: " + str(e))

    """def setAdminRightsAndTag(self, participants: list[CommunityParticipant]): #obsolete
        assert isinstance(participants, list), "participants must be type of list"
        try:
            LOG.debug("Start process of setting admin rights and tag")
            def truncateToNearestWeek(date):
                # Here, week starts on Monday
                return date - timedelta(days=date.weekday())

            participants.sort(key=lambda participant: truncateToNearestWeek(participant.sbt.received))

            groupedByDate = {
                k: list(v) for k, v in groupby(participants, key=lambda participant: truncateToNearestWeek(participant.sbt.received))
            }

            latestElectionDate, participants = list(groupedByDate.items())[-1]

            maxRound: int = 0
            for participant in participants:
                if participant.sbt.round > maxRound:
                    maxRound = participant.sbt.round
            LOG.debug("Highest level of last election is: " + str(maxRound))

            #


        except Exception as e:
            LOG.exception("Error in setAdminRightsAndTag: " + str(e))
            raise CommunityGroupException("Error in setAdminRightsAndTag: " + str(e))"""

    def sendCurrentGroupStateToAdmin(self, adminTelegram: str, participants: list[CustomMember]):
        assert isinstance(adminTelegram, str), "adminTelegram must be type of string"
        assert isinstance(participants, list), "participants must be type of list"
        try:

            LOG.debug("Start process of sending state to admin")
            toSend: str = "Current state of community group:\n"
            self.communication.sendMessage(sessionType=SessionType.BOT,
                                           chatId=adminTelegram,
                                           text=toSend)
            toSend = "```python"
            counter: int = 0
            for participant in participants:

                participantToStr: str = "Telegram id: " + str(participant.userId)
                participantToStr += ", Username: " + (str(participant.username) if participant.username is not None else "")
                participantToStr += ", Member status: " + str(participant.memberStatus)
                participantToStr += ", Is bot: " + ("true" if participant.isBot else "false")
                participantToStr += ", Tag: " + (str(participant.tag) if participant.tag is not None else "")
                participantToStr += ", Admin rights: " + (str(participant.adminRights) if participant.adminRights is not None else "NO")
                participantToStr += ", Promoted by: " + (str(participant.promotedBy) if participant.promotedBy is not None else "NO")

                toSend += participantToStr + "\n"
                counter += 1
                if counter == 20:
                    toSend += "\n ```"
                    isSent:bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                               chatId=adminTelegram,
                                               text=toSend)
                    toSend = "```python"
                    counter = 0
                    if isSent:
                        LOG.success("Message sent")
                    else:
                        LOG.error("Message not sent")

            if toSend != "```python":
                toSend += "\n ```"
                isSent: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                              chatId=adminTelegram,
                                                              text=toSend)
                if isSent:
                    LOG.success("Message sent")
                else:
                    LOG.error("Message not sent")
        except Exception as e:
            LOG.exception("Error in sendStateToAmin: " + str(e))
            raise CommunityGroupException("Error in sendStateToAmin: " + str(e))

    def do(self, contactAccount: str, executionTime: datetime, communityGroupID: int, electionCurrState: ElectCurrTable):
        assert isinstance(contactAccount, str), "contactAccount must be type of str"
        assert isinstance(executionTime, datetime), "executionTime must be type of datetime"
        assert isinstance(communityGroupID, int), "communityGroupID must be type of int"
        assert isinstance(electionCurrState, ElectCurrTable), "electionCurrState must be type of ElectCurrTable"
        try:
            LOG.debug("Start process of managing community group.")
            LOG.info("Check if bot has admin rights in community group - if anyone in the past"
                     " removed the bot from group of admins")

            RANGE_IN_DAYS_NFT = 31 * 9
            RANGE_IN_DAYS_INDUCTED = 31 * 3

            self.addGroupToKnownUsersAndCheckAdminRight(communityGroupID=communityGroupID)

            LOG.debug("...getting participants with NFT (goal state - not current members of community group...)")
            participantsGoalState: list[CommunityParticipant] = \
                self.getUsersWithNFT(contractAccount=contactAccount,
                                     rangeInDays=RANGE_IN_DAYS_NFT,
                                     executionTime=executionTime
                                     )
            if participantsGoalState is None:
                raise CommunityGroupException("There was an error when getting participants with NFT")

            LOG.debug("...getting participants who called inducted method on contract(last 3 months)...")
            inductedAccounts: list[Participant] = self.getActionInducted(contractAccount=contactAccount,
                                   executionTime=executionTime,
                                   rangeInDays=RANGE_IN_DAYS_INDUCTED)
            #only important thing in inductedAccounts are parameters telegram and account name

            if inductedAccounts is None:
                raise CommunityGroupException("There was an error when getting participants who called inducted "
                                              "method on contract")



            LOG.debug("...setting tag and admin rights ...")
            participantsGoalState: list[CommunityParticipant] = \
                self.setTagAndAdminRights(participantsGoal=participantsGoalState, electionCurrState=electionCurrState)


            LOG.debug("...getting participants in community group...")
            participantsInGroup: list[CustomMember] = self.getUsersFromCommunityGroup(communityGroupID=communityGroupID)

            self.sendCurrentGroupStateToAdmin(adminTelegram=telegram_admins_id[0],
                                              participants=participantsInGroup
                                              )

            if participantsInGroup is None:
                raise CommunityGroupException("There was an error when getting users from community group")

            currentState: list[CommunityParticipant] = self.fromCustomMembersToCommunityParticipants(
                                                                customMembers=participantsInGroup,
                                                                contractAccount=contactAccount,
                                                                rangeInDays=RANGE_IN_DAYS_NFT,
                                                                executionTime=executionTime
                                                            )



            LOG.debug("Starting the process of managing community group.")
            communityList: CommunityList = CommunityList(inducted=inductedAccounts)
            #add goal state to the object
            for item in participantsGoalState:
                communityList.append(state=CommunityListState.GOAL, item=item)

            #add current state to the object
            for item in currentState:
                communityList.append(state=CommunityListState.CURRENT, item=item)

            self.manipulateCommunityGroup(communityGroupID=communityGroupID, communityList=communityList,
                                          adminTelegram=telegram_admins_id[0])

        except Exception as e:
            LOG.exception("Error in do: " + str(e))
            raise CommunityGroupException("Error in do: " + str(e))
