from enum import Enum

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup

from app.chain.dfuse import DfuseConnection
from app.constants import dfuse_api_key, time_span_for_notification, \
    alert_message_time_election_is_coming, eden_portal_url, telegram_admins_id, ReminderGroup
from app.database import Election, Database
from app.log import Log
from datetime import datetime, timedelta
from app.chain.eden import EdenData, Response, ResponseError
from app.database.participant import Participant
from app.database.reminder import Reminder, ReminderSent, ReminderSendStatus
from datetime import datetime
from app.debugMode.modeDemo import ModeDemo
from app.dateTimeManagement import DateTimeManagement
from app.transmission import SessionType, Communication

import gettext

from app.transmission.name import ADD_AT_SIGN_IF_NOT_EXISTS

_ = gettext.gettext
__ = gettext.ngettext


class ReminderManagementException(Exception):
    pass


LOG = Log(className="RemindersManagement")


class ReminderManagement:

    def __init__(self, database: Database, edenData: EdenData, communication: Communication, modeDemo: ModeDemo = None):
        assert isinstance(database, Database), "database is not instance of Database"
        assert isinstance(edenData, EdenData), "edenData is not instance of EdenData"
        assert isinstance(communication, Communication), "communication is not instance of Communication"
        assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo is not instance of ModeDemo or None"

        self.database: Database = database

        self.edenData = edenData
        self.communication = communication

        self.dateTimeManagement = DateTimeManagement(edenData=edenData)
        self.participants = []

        self.datetime = self.setExecutionTime(modeDemo=modeDemo)

        # basic workflow
        self.election: Election = self.getLastElection()
        #if self.database.electionGroupsCreated(election= self.election, round= 999) #TODO: check in the future
        #    self.createRemindersIfNotExists(election=self.election)

    def getLastElection(self) -> Election:
        """Get last election"""
        try:
            LOG.info("Get last election")
            election: Election = self.database.getLastElection()
            if election is not None:
                LOG.debug("Last election: " + str(election))
                return election
            else:
                raise Exception("Last election is not set in the database. Something went wrong.")
                return None
        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException("Exception thrown when called getLastElection; Description: " + str(e))

    def createRemindersIfNotExists(self, election: Election):
        """Create reminder if there is no reminder in database"""
        try:
            LOG.info("Create reminders")
            self.database.createRemindersIfNotExists(election=election)
            LOG.debug("Reminders created")

        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException(
                "Exception thrown when called getParticipantsFromChainAndMatchWithDatabase; Description: " + str(e))

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

    def sendReminderIfNeeded(self, election: Election, modeDemo: ModeDemo = None):
        """Send reminder if needed"""
        try:
            LOG.info("Send reminders if needed")

            executionTime = self.setExecutionTime(modeDemo=modeDemo)
            LOG.debug("Working time: " + str(executionTime))

            reminders = self.database.getReminders(election=election)
            if reminders is not None:
                for item in reminders:
                    if isinstance(item, Reminder):
                        reminder: Reminder = item
                        LOG.info("Reminder: " + str(reminder))
                        LOG.debug("Reminder time: " + str(reminder.dateTimeBefore) +
                                  "; Execution time: " + str(executionTime) +
                                  "; Reminder time span: " + str(reminder.dateTimeBefore + timedelta(
                                                                    minutes=time_span_for_notification)) +
                                  " ..."
                                  )

                        if reminder.dateTimeBefore < executionTime < reminder.dateTimeBefore + timedelta(
                                minutes=time_span_for_notification):
                            LOG.info("... send reminder to election id: " + str(reminder.electionID) +
                                     " and dateTimeBefore: " + str(reminder.dateTimeBefore))
                            members: list[Participant] = self.getMembersFromDatabase(election=election)
                            reminderSentList: list[ReminderSent] = self.database.getAllParticipantsReminderSentRecord(
                                reminder=reminder)
                            for member in members:
                                if member.telegramID is None or len(member.telegramID) < 3:
                                    LOG.debug("Member " + str(member) + " has no known telegramID, skip sending")
                                    continue

                                isSent: bool = self.sendAndSyncWithDatabase(member=member,
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
        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException(
                "Exception thrown when called sendReminderIfNeeded; Description: " + str(e))

    def getMembersFromChain(self, height: int = None):
        """Get participants from chain"""
        try:
            LOG.info("Get members from chain")
            response: Response = self.edenData.getMembers(height=height)
            if isinstance(response, ResponseError):
                raise Exception("Response from chain is not instance of Response; Description: " + str(response))
            else:
                return response.data
        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException \
                ("Exception thrown when called getMembersFromChain; Description: " + str(e))

    def getMembersFromDatabase(self, election: Election):
        """Get participants from database"""
        try:
            LOG.info("Get members from database")
            participants = self.database.getMembers(election=election)
            if participants is not None:
                return participants
            else:
                raise Exception("Participants are not set in the database. Something went wrong.")
                return None
        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException(
                "Exception thrown when called getMembersFromDatabase; Description: " + str(e))

    def theNearestDateTime(self, alerts: list[[int, ReminderGroup, str]], minutes: int) -> tuple[
        int, ReminderGroup, str]:
        """Get the nearest date time"""
        try:
            LOG.info("Get nearest date time")
            nearest = min(alerts, key=lambda x: abs(x[0] - minutes))
            return nearest
        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException(
                "Exception thrown when called nearestDateTime; Description: " + str(e))

    def getTextForUpcomingElection(self, member: Participant, electionDateTime: datetime, reminder: Reminder,
                                   currentTime: datetime) -> str:
        try:
            LOG.info("Getting text for election: " + str(electionDateTime))

            assert isinstance(electionDateTime, datetime)
            assert isinstance(currentTime, datetime)
            assert isinstance(reminder, Reminder)
            assert isinstance(member, Participant)

            # get timedifference in text format from constants
            minutesToElectionInMinutes = (electionDateTime - currentTime).total_seconds() / 60
            nearestDatetimeToElectionInMinutes: tuple[int, ReminderGroup, str] = self.theNearestDateTime(
                alert_message_time_election_is_coming,
                minutesToElectionInMinutes)
            nearestDateTimeText = nearestDatetimeToElectionInMinutes[2]
            LOG.debug("Nearest datetime to election: " + str(
                nearestDatetimeToElectionInMinutes) + " minutes with text '" + nearestDateTimeText + "'")

            LOG.debug("Member: " + str(member))
            if member.participationStatus and \
                    (nearestDatetimeToElectionInMinutes[1] == ReminderGroup.BOTH or
                     nearestDatetimeToElectionInMinutes[1] == ReminderGroup.ATTENDED):
                LOG.debug("Member is going to participate and reminder is for 'attended members'")
                return _("Hey! \n"
                         "I'am here to remind you that election is starting %s.") % \
                       (nearestDateTimeText)

            elif member.participationStatus is False and \
                    (nearestDatetimeToElectionInMinutes[1] is ReminderGroup.BOTH or \
                     nearestDatetimeToElectionInMinutes[1] is ReminderGroup.NOT_ATTENDED):
                LOG.debug("Member is going to participate and reminder is for 'not attended members'")
                return _("Hey! \n"
                         "I'am here to remind you that election is starting %s."
                         " \n You are not attending this election, so you will not be able to participate.\n\n"
                         "You can change your attendance status by pressing the button below text:.") % \
                       (nearestDateTimeText)
            else:
                return ""
        except Exception as e:
            LOG.exception("Exception (in getTextForUpcomingElection): " + str(e))
            raise ReminderManagementException("Exception (in getTextForUpcomingElection): " + str(e))

    def sendAndSyncWithDatabase(self, member: Participant, election: Election, reminder: Reminder,
                                reminderSentList: list[ReminderSent],
                                modeDemo: ModeDemo = None) -> bool:
        """Send reminder and write to database"""
        try:
            assert isinstance(member, Participant), "member is not instance of Participant"
            assert isinstance(election, Election), "election is not instance of Election"
            assert isinstance(reminderSentList, list), "reminderSentList is not instance of list"
            LOG.trace("Send and sync with database")
            LOG.trace("Member: " + str(member))
            LOG.trace("Election id: " + str(election.electionID))

            foundReminders: list[ReminderSent] = [x for x in reminderSentList if x.accountName == member.accountName]

            # if participant is found in reminderSentList + status is sent then skip
            if len(foundReminders) > 0:
                LOG.debug("Participant is found in reminderSentList + status is 'SEND'")
                LOG.info("Reminder already sent to telegramID: " + str(member.telegramID))
                return

            # prepare and send notification to the user

            text: str = self.getTextForUpcomingElection(member=member,
                                                        electionDateTime=election.date,
                                                        reminder=reminder,
                                                        currentTime=self.datetime)
            if text is None or len(text) < 1:
                LOG.info("Text is empty, skip sending")
                return False
            replyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                [
                    [  # First row
                        InlineKeyboardButton(  # Opens a web URL
                            "Change the status",
                            url=eden_portal_url
                        ),
                    ]
                ]
            ) if member.participationStatus is False else None

            # be sure that next comparison is correct, because we really do not want to send fake messages to
            # users

            sendResponse: bool

            if modeDemo is None:
                # LIVE MODE
                LOG.trace("Live mode is enabled, sending message to: " + member.telegramID)
                sendResponse = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                              chatId=member.telegramID,
                                                              text=text,
                                                              inlineReplyMarkup=replyMarkup)

                LOG.info("LiveMode; Is message sent successfully to " + member.telegramID + ": " + str(sendResponse)
                         + ". Saving to the database under electionID: " + str(election.electionID))

                self.database.createOrUpdateReminderSentRecord(reminder=reminder, accountName=member.accountName,
                                                           sendStatus=ReminderSendStatus.SEND if sendResponse is True
                                                           else ReminderSendStatus.ERROR)

            else:
                # DEMO MODE
                LOG.trace("Demo mode is enabled, sending message to admins")
                for admin in telegram_admins_id:
                    text = text + "\n\n" + "Demo mode is enabled, sending message to " + admin + " instead of " + \
                           ADD_AT_SIGN_IF_NOT_EXISTS(member.telegramID)
                    sendResponse = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                                  chatId=admin,
                                                                  text=text,
                                                                  inlineReplyMarkup=replyMarkup)

                    LOG.info("DemoMode; Is message sent successfully to " + admin + ": " + str(sendResponse)
                             + ". Saving to the database under electionID: " + str(election.electionID))

                    self.database.createOrUpdateReminderSentRecord(reminder=reminder, accountName=member.accountName,
                                                               sendStatus=ReminderSendStatus.SEND
                                                               if sendResponse is True
                                                               else ReminderSendStatus.ERROR)

            LOG.debug("Sending to participant: " + member.telegramID + " text: " + text)
            return sendResponse

        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException(
                "Exception thrown when called sendReminderAndWriteToDatabase; Description: " + str(e))
