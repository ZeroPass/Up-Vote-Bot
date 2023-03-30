from datetime import datetime, timedelta
from enum import Enum

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from chain import EdenData
from chain.dfuse import DfuseConnection, GraphQLApi
from chain.stateElectionState import ElectCurrTable
from constants import alert_message_time_upload_video, ReminderGroup, time_span_for_notification_upload_video, \
    telegram_bot_name, default_language
from database import Database, Election, Reminder, ReminderSent, ReminderSendStatus
from database.participant import Participant
from database.room import Room
from dateTimeManagement import DateTimeManagement
from debugMode.modeDemo import ModeDemo
from log import Log

import gettext

from text.textManagement import VideoReminderTextManagement, Button
from transmission import Communication, SessionType
from transmission.name import ADD_AT_SIGN_IF_NOT_EXISTS

_ = gettext.gettext
__ = gettext.ngettext


class AfterElectionReminderManagementException(Exception):
    pass


LOG = Log(className="AfterElectionReminderManagement")


class AfterElectionReminderManagement:

    def __init__(self, database: Database, edenData: EdenData, communication: Communication,
                 modeDemo: ModeDemo = None):
        assert isinstance(database, Database), "database must be type of Database"
        assert isinstance(edenData, EdenData), "edenData must be type of EdenData"
        assert isinstance(communication, Communication), "communication must be type of Communication"
        assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be type of ModeDemo or None"
        try:
            LOG.info("Init AfterElectionReminderManagement")
            self.database: Database = database

            self.edenData = edenData
            self.communication = communication

            self.dateTimeManagement = DateTimeManagement(edenData=edenData)
            self.participants = []

            self.datetime = self.setExecutionTime(modeDemo=modeDemo)

        except Exception as e:
            LOG.exception("Error in AfterElectionReminderManagement: " + str(e))
            raise AfterElectionReminderManagementException("Error in AfterElectionReminderManagement.init: " + str(e))

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

    def createRemindersUploadVideoIfNotExists(self, election: Election, deadlineInMinutes: int):
        """Create reminders to upload video if not exists"""
        assert isinstance(election, Election), "election must be type of Election"
        assert isinstance(deadlineInMinutes, int), "deadlineInMinutes must be type of int"  # 2 weeks = 60 * 24 * 14
        try:
            LOG.info("Create reminders (upload video) in election if not exists")

            if self.database.getRemindersCount(election=election, reminderGroup1=ReminderGroup.UPLOAD_VIDEO) == \
                    len(alert_message_time_upload_video):
                LOG.debug(message="Reminders(upload video) for election:" + str(election.electionID) + " already exist")
                return

            session = self.database.createCsesion(expireOnCommit=False)

            for item in alert_message_time_upload_video:
                if len(item) != 3:
                    raise AfterElectionReminderManagementException("alert_message_time_upload_video  struct "
                                                                   "is not in correct size")
                if isinstance(item[0], int) is False:
                    LOG.exception("alert_message_time_election_is_coming tuple[0]: "
                                  "element is not int")

                    raise AfterElectionReminderManagementException("alert_message_time_upload_video tuple[0]: "
                                                                   "element is not int")
                if isinstance(item[1], Enum) is False:
                    LOG.exception("alert_message_time_election_is_coming tuple[1]: "
                                  "element is not ReminderGroup")

                    raise AfterElectionReminderManagementException("alert_message_time_upload_video tuple[1]: "
                                                                   "element is not ReminderGroup")
                if isinstance(item[2], str) is False:
                    LOG.exception("alert_message_time_election_is_coming tuple[2]: "
                                  "element is not str")

                    raise AfterElectionReminderManagementException("alert_message_time_upload_video tuple[2]: "
                                                                   "element is not str")

                deadlineDT = election.date + timedelta(minutes=deadlineInMinutes)
                LOG.info("Deadline for upload video: " + str(deadlineDT))

                reminder = Reminder(electionID=election.electionID,
                                    reminderGroup=item[1],
                                    dateTimeBefore=deadlineDT - timedelta(minutes=item[0]))
                self.database.createReminder(reminder=reminder, csession=session)

            session.close()
            LOG.debug("Reminders created")
        except Exception as e:
            session.close()
            LOG.exception("Exception thrown when called createRemindersIFNotExists; Description: " + str(e))

    def getMembersAndRoomsFromDatabase(self, election: Election):
        """Get participants from database"""
        try:
            LOG.info("Get members from database")
            roomsAndParticipants = self.database.getMembers(election=election)
            if roomsAndParticipants is not None:
                return roomsAndParticipants
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
            raise AfterElectionReminderManagementException("Exception thrown when called nearestDateTime; Description: " + str(e))

    def getTextForVideoUploadReminder(self, election: Election, room: Room, deadlineInMinutes: int,
                                      currentTime: datetime, vRtextManagement: VideoReminderTextManagement) -> str:
        try:
            LOG.info("Creating text for video reminder for election: " + str(election))
            assert isinstance(election, Election), "election must be type of Election"
            assert isinstance(room, Room), "room must be type of Room"
            assert isinstance(deadlineInMinutes, int), "deadlineInMinutes must be type of int"
            assert isinstance(currentTime, datetime), "currentTime must be type of datetime"
            assert isinstance(vRtextManagement, VideoReminderTextManagement), "vRtextManagement must be type of " \
                                                                              "VideoReminderTextManagement"

            deadlineDT: datetime = election.date + timedelta(minutes=deadlineInMinutes)
            LOG.info("Deadline for upload video: " + str(deadlineDT))

            # get timedifference in text format from constants
            minutesToElectionInMinutes = (deadlineDT - currentTime).total_seconds() / 60
            nearestDatetimeToFinishUploadInMinutes: tuple[int, ReminderGroup, str] = self.theNearestDateTime(
                alert_message_time_upload_video,
                minutesToElectionInMinutes)
            nearestDateTimeText = nearestDatetimeToFinishUploadInMinutes[2]
            LOG.debug(
                "Nearest datetime to end of upload period of video: " + str(nearestDatetimeToFinishUploadInMinutes) +
                " minutes with text '" + nearestDateTimeText + "'")

            text: str = vRtextManagement.videoReminder(round=room.round + 1,
                                                       group=room.roomIndex + 1,
                                                       expiresText=nearestDateTimeText)
            return text
        except Exception as e:
            LOG.exception("Exception (in getTextForVideoUploadReminder): " + str(e))
            raise AfterElectionReminderManagementException("Exception (in getTextForVideoUploadReminder): " + str(e))

    def sendAndSyncWithDatabaseUploadVideoNotif(self,
                                                member: Participant,
                                                room: Room,
                                                election: Election,
                                                reminder: Reminder,
                                                reminderSentList: list[ReminderSent],
                                                deadlineInMinutes: int,
                                                modeDemo: ModeDemo = None) -> bool:
        """Send reminder and write to database"""
        try:
            assert isinstance(member, Participant), "member is not instance of Participant"
            assert isinstance(room, Room), "room is not instance of Room"
            assert isinstance(election, Election), "election is not instance of Election"
            assert isinstance(reminder, Reminder), "reminder is not instance of Reminder"
            assert isinstance(reminderSentList, list), "reminderSentList is not instance of list"
            assert isinstance(deadlineInMinutes, int), "deadlineInMinutes is not instance of int"
            assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be type of ModeDemo or None"

            LOG.trace("Send and sync with database. "
                      "Election id: " + str(election.electionID) +
                      ", member: " + str(member) +
                      ", room: " + str(room))

            foundReminders: list[ReminderSent] = [x for x in reminderSentList if x.accountName == member.accountName]

            # if participant is found in reminderSentList + status is sent then skip
            if len(foundReminders) > 0:
                LOG.debug("Participant is found in reminderSentList + status is 'SEND'")
                LOG.info("Reminder already sent to telegramID: " + str(member.telegramID))
                return

            # prepare and send notification to the user
            # RawActionWeb().electVideo(round=reminder.round,
            #                                             voter=member.accountName,
            #                                             candidate=None)

            vRtextManagement: VideoReminderTextManagement = VideoReminderTextManagement(language=default_language)

            uploadReminderText: str = self.getTextForVideoUploadReminder(election=election,
                                                                         room=room,
                                                                         deadlineInMinutes=deadlineInMinutes,
                                                                         currentTime=datetime.now(),
                                                                         vRtextManagement=vRtextManagement)

            buttonsUploadReminder: tuple(Button) = \
                vRtextManagement.videoReminderButtonText(groupLink=room.shareLink)

            if len(buttonsUploadReminder) != 2:
                raise AfterElectionReminderManagementException("buttonsUploadReminder must have 2 elements")

            replyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                [
                    [  # First row
                        InlineKeyboardButton(
                            text=buttonsUploadReminder[0]['text'],
                            url=buttonsUploadReminder[0]['value']
                        ),
                        InlineKeyboardButton(
                            text=buttonsUploadReminder[1]['text'],
                            url=buttonsUploadReminder[1]['value']
                        ),
                    ]
                ]
            )

            sendResponse: bool = False

            try:
                cSession = self.database.createCsesion()
                LOG.trace("Live mode is enabled, sending message to: " + member.telegramID)
                member.telegramID = ADD_AT_SIGN_IF_NOT_EXISTS(member.telegramID)
                sendResponse = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                              chatId=member.telegramID,
                                                              text=uploadReminderText,
                                                              inlineReplyMarkup=replyMarkup)

                LOG.info("LiveMode; Is message sent successfully to " + member.telegramID + ": " + str(sendResponse)
                         + ". Saving to the database under electionID: " + str(election.electionID))

                response: bool = self.database.createOrUpdateReminderSentRecord(reminder=reminder,
                                                                                accountName=member.accountName,
                                                                                sendStatus=ReminderSendStatus.SEND if sendResponse is True
                                                                                else ReminderSendStatus.ERROR,
                                                                                cSession=cSession)
                if response is True:
                    self.database.commitCcession(session=cSession)
                else:
                    self.database.rollbackCcession(session=cSession)
                self.database.removeCcession(session=cSession)
            except Exception as e:
                LOG.exception("Exception in sendAndSyncWithDatabaseUploadVideoNotification.inside. Description: " +
                              str(e))
                self.database.rollbackCcession(session=cSession)
                self.database.removeCcession(session=cSession)
            return sendResponse

        except Exception as e:
            LOG.exception("Exception (in sendAndSyncWithDatabaseUploadVideoNotification): " + str(e))

    def isVideoReminderTimeframe(self, executionTime: datetime, electionDate: datetime, deadlineInMinutes: int) -> bool:
        """Check if it is time to send reminder"""
        try:
            assert isinstance(executionTime, datetime), "executionTime is not instance of datetime"
            assert isinstance(electionDate, datetime), "electionDate is not instance of datetime"
            assert isinstance(deadlineInMinutes, int), "deadlineInMinutes is not instance of int"

            LOG.trace("Check if it is time to send reminder. "
                      "executionTime: " + str(executionTime) +
                      ", electionDate: " + str(electionDate) +
                      ", deadlineInMinutes: " + str(deadlineInMinutes))

            deadlineDate: datetime = electionDate + timedelta(minutes=deadlineInMinutes)

            if executionTime <= deadlineDate:
                LOG.info("We are in the timeframe to send reminder")
                return True
            else:
                LOG.info("We are NOT in the timeframe to send reminder")
                return False
        except Exception as e:
            LOG.exception("Exception (in isVideoReminderTimeframe): " + str(e))
            raise AfterElectionReminderManagementException("Exception (in isVideoReminderTimeframe): " + str(e))

    def sendReminderUploadVideIfNeeded(self, currentElection: Election, deadlineInMinutes: int,
                                       electCurr: ElectCurrTable = None,  modeDemo: ModeDemo = None):
        assert isinstance(currentElection, Election), "currentElection must be type of Election"
        assert isinstance(deadlineInMinutes, int), "deadlineInMinutes must be type of int"
        assert isinstance(electCurr, (ElectCurrTable, type(None))), "electCurr must be type of ElectCurrTable or None"
        assert isinstance(modeDemo, (ModeDemo, type(None))), "modeDemo must be type of ModeDemo or None"
        """Send reminder to group and participants if needed"""
        try:
            LOG.info("Send reminder to group and participants if needed")
            if electCurr is None:
                LOG.error("electCurr is None. Something went wrong when getting/parsing elect.Curr table."
                          "Do not send any reminders")
                return
            if electCurr.getLastElectionTime() is None or \
                    isinstance(electCurr.getLastElectionTime(), datetime) is False:
                LOG.error("electCurr.getLastElectionTime() is not datetime. Something went wrong when getting/parsing "
                          "elect.Curr table. Do not send any reminders")
                return

            #get last election if exsists in database
            previousElection: Election = self.database.getElectionByDate(contract=currentElection.contract,
                                                                         date=electCurr.getLastElectionTime())

            if previousElection is None:
                LOG.error("previousElection is not found in the database."
                          "Do not send any reminders")
                return



            executionTime: datetime = self.setExecutionTime(modeDemo=modeDemo)
            LOG.debug("Working time: " + str(executionTime))

            if self.isVideoReminderTimeframe(executionTime=executionTime,
                                             electionDate=electCurr.getLastElectionTime(),
                                             deadlineInMinutes=deadlineInMinutes) is False:
                LOG.debug("It is not time to send reminder")
                return


            reminders = self.database.getReminders(election=previousElection, reminderGroup1=ReminderGroup.UPLOAD_VIDEO)
            if reminders is not None:
                for item in reminders:
                    if isinstance(item, Reminder):
                        reminder: Reminder = item
                        LOG.info("Reminder: " + str(reminder) + " ...")

                        if reminder.dateTimeBefore <= executionTime < reminder.dateTimeBefore + timedelta(
                                minutes=time_span_for_notification_upload_video):
                            LOG.info("... is between time span for notification. Send it if not sent yet")
                            # get all participants who participate in election (grouped by roomID)
                            roomsAndMembers: list[Participant] = \
                                self.getMembersAndRoomsFromDatabase(election=previousElection)

                            #  get reminders that were already sent
                            reminderSentList: list[ReminderSent] = \
                                self.database.getAllParticipantsReminderSentRecord(reminder=reminder)

                            #  update known users - just to be sure that all known users are in local database
                            self.communication.updateKnownUserData(botName=telegram_bot_name)

                            for room, member in roomsAndMembers:
                                if member.telegramID is None or len(member.telegramID) < 3:
                                    LOG.debug("Member " + str(member) + " has no known telegramID, skip sending")
                                    continue

                                isSent: bool = \
                                    self.sendAndSyncWithDatabaseUploadVideoNotif(member=member,
                                                                                 room=room,
                                                                                 election=previousElection,
                                                                                 reminder=reminder,
                                                                                 reminderSentList=reminderSentList,
                                                                                 deadlineInMinutes=deadlineInMinutes,
                                                                                 modeDemo=modeDemo)
                                if isSent:
                                    LOG.info("Reminder (for user: " + member.accountName + " sent to telegramID: "
                                             + member.telegramID)

                        else:
                            LOG.debug("... reminder is not needed!")
            else:
                LOG.error("Reminders are not set in the database. Something went wrong.")
        except Exception as e:
            LOG.exception("Exception thrown when called sendReminderIfNeeded; Description: " + str(e))

    def getActionsVideoUploaded(self, account: str, startBlockNum: int, endBlockNum: int) -> list:  # made by bot
        assert isinstance(account, str), "account must be type of str"  # where smart contract is deployed
        assert isinstance(startBlockNum, int), "startBlockNum must be type of int"
        assert isinstance(endBlockNum, int), "endBlockNum must be type of int"
        try:
            LOG.debug("Check if video is uploaded on account: " + account +
                      " from block: " + str(startBlockNum) +
                      " to block: " + str(endBlockNum))

            actionsVideoUploaded = self.graphQLApi.getActionsVideoUploaded(account=account,
                                                                           startBlockNum=startBlockNum,
                                                                           endBlockNum=endBlockNum)
            return actionsVideoUploaded
        except Exception as e:
            LOG.exception("Error in AfterElectionReminderManagement.getActionsVideoUploaded: " + str(e))
            raise AfterElectionReminderManagementException(
                "Error in AfterElectionReminderManagement.getActionsVideoUploaded: " + str(e))

    def getActionsVideoUploadedFromBlock(self, account: str, startBlockNum: int) -> list:  # made by bot
        assert isinstance(account, str), "account must be type of str"  # where smart contract is deployed
        assert isinstance(startBlockNum, int), "startBlockNum must be type of int"
        try:
            LOG.debug("Check if video is uploaded on account: " + account +
                      " from block: " + str(startBlockNum))

            actionsVideoUploaded = self.graphQLApi.getActionsVideoUploadedFromBlock(account=account,
                                                                                    startBlockNum=startBlockNum)
            return actionsVideoUploaded
        except Exception as e:
            LOG.exception("Error in AfterElectionReminderManagement.getActionsVideoUploadedFrom")
