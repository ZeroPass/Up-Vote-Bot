from enum import Enum

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup

from chain.dfuse import DfuseConnection, ResponseSuccessful
from constants import dfuse_api_key, time_span_for_notification, \
    alert_message_time_election_is_coming, eden_portal_url, telegram_admins_id, ReminderGroup, \
    time_span_for_notification_time_is_up, alert_message_time_round_end_is_coming, eden_portal_url_action, \
    telegram_bot_name
from constants.rawActionWeb import RawActionWeb
from database import Election, Database, ExtendedParticipant, ExtendedRoom
from database.room import Room
from groupManagement import RoomArray
from log import Log
from datetime import datetime, timedelta
from chain.eden import EdenData, Response, ResponseError
from database.participant import Participant
from database.reminder import Reminder, ReminderSent, ReminderSendStatus
from datetime import datetime
from debugMode.modeDemo import ModeDemo
from dateTimeManagement import DateTimeManagement
from text.textManagement import GroupCommunicationTextManagement
from transmission import SessionType, Communication

import gettext

from transmission.name import ADD_AT_SIGN_IF_NOT_EXISTS

_ = gettext.gettext
__ = gettext.ngettext


class ReminderManagementException(Exception):
    pass


LOG = Log(className="RemindersManagement")


class ReminderManagement:

    def __init__(self, election: Election, database: Database, edenData: EdenData, communication: Communication, modeDemo: ModeDemo = None):
        assert isinstance(election, Election), "election is not instance of Election"
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
        self.election: Election = election
        # if self.database.electionGroupsCreated(election= self.election, round= 999) #TODO: check in the future
        #    self.createRemindersIfNotExists(election=self.election)

    def createRemindersTimeIsUpIfNotExists(self, election: Election, round: int, roundEnd: datetime):
        """Create round end reminders if not exists"""
        try:
            LOG.info("Create reminders (time is up) in election if not exists")
            session = self.database.createCsesion(expireOnCommit=False)
            for item in alert_message_time_round_end_is_coming:
                if len(item) != 3:
                    raise ReminderManagementException("alert_message_time_round_end_is_coming is not in correct size")
                if isinstance(item[0], int) is False:
                    LOG.exception("alert_message_time_round_end_is_coming tuple[0]: "
                                  "element is not int")

                    raise ReminderManagementException("alert_message_time_round_end_is_coming tuple[0]: "
                                                      "element is not int")
                if isinstance(item[1], Enum) is False:
                    LOG.exception("alert_message_time_round_end_is_coming tuple[1]: "
                                  "element is not ReminderGroup")

                    raise ReminderManagementException("alert_message_time_round_end_is_coming tuple[1]: "
                                                      "element is not ReminderGroup")
                if isinstance(item[2], str) is False:
                    LOG.exception("alert_message_time_round_end_is_coming tuple[2]: "
                                  "element is not str")

                    raise ReminderManagementException("alert_message_time_round_end_is_coming tuple[2]: "
                                                      "element is not str")

                reminder = Reminder(electionID=election.electionID,
                                    round=round,
                                    reminderGroup=item[1],
                                    dateTimeBefore=roundEnd - timedelta(minutes=item[0]))
                self.database.createReminder(reminder=reminder, csession=session)

            session.close()
            LOG.debug("Reminders created")
        except Exception as e:
            session.close()
            LOG.exception("Exception thrown when called createRemindersIFNotExists; Description: " + str(e))

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

    def sendReminderTimeIsUpIfNeeded(self, election: Election, roundEnd: datetime, modeDemo: ModeDemo = None):
        """Send reminder if time is up"""
        try:
            LOG.info("Send reminder if time is up")
            self.communication.updateKnownUserData(botName=telegram_bot_name)
            executionTime: datetime = self.setExecutionTime(modeDemo=modeDemo)

            reminders: list = self.database.getReminders(election=election, reminderGroup1=ReminderGroup.IN_ELECTION)
            if reminders is not None:
                for reminder in reminders:
                    reminderRound: int = reminder.round
                    LOG.info("Reminder (time is up): " + str(reminder))
                    LOG.debug("Reminder (time is up) time: " + str(reminder.dateTimeBefore) +
                              "; Execution time: " + str(executionTime) +
                              "; Reminder time span: " + str(reminder.dateTimeBefore + timedelta(
                        minutes=time_span_for_notification_time_is_up)) +
                              " ..."
                              )
                    if reminder.dateTimeBefore <= executionTime <= reminder.dateTimeBefore + timedelta(
                            minutes=time_span_for_notification_time_is_up):

                        LOG.info("... send reminder to election id: " + str(reminder.electionID) +
                                 " and dateTimeBefore: " + str(reminder.dateTimeBefore) +
                                 " and round: " + str(reminder.round))

                        # get text of reminder
                        minutesToElectionInMinutes = (roundEnd - executionTime).total_seconds() / 60
                        closestReminder: tuple[int, ReminderGroup, str] = self.theNearestDateTime(
                            alert_message_time_round_end_is_coming,
                            minutesToElectionInMinutes)

                        roomsAndParticipants: list[list(Room, Participant)] = self.getMembersFromDatabaseInElection(
                            election=election,
                            reminder=reminder)

                        if roomsAndParticipants is None or len(roomsAndParticipants) == 0:
                            LOG.warning("All participant got reminder - do nothing")
                            return

                        votes: Response = self.edenData.getVotes(
                            height=modeDemo.currentBlockHeight if modeDemo is not None else None)

                        if isinstance(votes, ResponseError):
                            LOG.error("Error when called getVotes: " + votes.error)
                            raise ReminderManagementException("Error when called getVotes: " + votes.error)

                        if len(roomsAndParticipants) == 0:
                            LOG.critical("No rooms and participants")
                            return

                        # extendedRoom = ExtendedRoom.fromRoom(room= )
                        roomArray: RoomArray = RoomArray()
                        currentRoom: ExtendedRoom = None
                        self.communication.updateKnownUserData(botName=telegram_bot_name)
                        for room, participant in roomsAndParticipants:
                            LOG.debug("Group: " + str(room) + "; Participant: " + str(participant))

                            # only first time
                            if currentRoom is None:
                                currentRoom = ExtendedRoom.fromRoom(room=room)
                                roomArray.setRoom(room=currentRoom)

                            # if current room is not the same as previous, add it to the array
                            if currentRoom.roomID != room.roomID:
                                currentRoom = ExtendedRoom.fromRoom(room=room)
                                roomArray.setRoom(room=currentRoom)

                            # create extended participant - because of 'votefor' variable
                            extendedParticipant: ExtendedParticipant = \
                                ExtendedParticipant.fromParticipant(participant=participant,
                                                                    index=0  # index does not matter here
                                                                    )

                            # send to participant
                            # check if participant has voted
                            candidate = [y['candidate'] for x, y in votes.data.items() if
                                         x == extendedParticipant.accountName and y is not None]

                            # set vote
                            extendedParticipant.voteFor = candidate[0] if len(candidate) > 0 else None

                            # add participant to current room
                            currentRoom.addMember(member=extendedParticipant)

                            self.sendAndSyncWithDatabaseRoundIsAlmostFinish(member=extendedParticipant,
                                                                            reminder=reminder,
                                                                            modeDemo=modeDemo,
                                                                            election=election,
                                                                            closestReminderConst=closestReminder
                                                                            )

                        # send message to the group
                        self.sendToTheGroupTimeIsUp(reminderRound=reminderRound,
                                                    election=election,
                                                    closestReminderConst=closestReminder,
                                                    roomArray=roomArray,
                                                    modeDemo=modeDemo)

        except Exception as e:
            LOG.exception("Exception thrown when called sendReminderTimeIsUpIfNeeded; Description: " + str(e))

    def sendReminderIfNeeded(self, election: Election, modeDemo: ModeDemo = None):
        """Send reminder if needed"""
        try:
            LOG.info("Send reminders if needed")
            executionTime: datetime = self.setExecutionTime(modeDemo=modeDemo)
            LOG.debug("Working time: " + str(executionTime))

            reminders: list[Reminder] = self.database.getReminders(election=election,
                                                                   reminderGroup1=ReminderGroup.ATTENDED,
                                                                   reminderGroup2=ReminderGroup.NOT_ATTENDED)
            remindersBoth: list[Reminder] = self.database.getReminders(election=election,
                                                                       reminderGroup1=ReminderGroup.BOTH)
            if reminders is None and remindersBoth is not None:
                reminders = remindersBoth
            elif reminders is not None and remindersBoth is None:
                # do nothing
                Log.info("reminders is not None and remindersBoth is None")
            elif reminders is not None and remindersBoth is not None:
                reminders = reminders + remindersBoth

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

                            dummyElection: Election = self.database.getDummyElection(election=election)
                            if dummyElection is None:
                                LOG.error("HUGE PROBLEM: Dummy election is not found. Reminders will not be sent")
                                return

                            members: list[(Room, Participant)] = self.getMembersFromDatabase(election=dummyElection)
                            reminderSentList: list[ReminderSent] = self.database.getAllParticipantsReminderSentRecord(
                                reminder=reminder)
                            self.communication.updateKnownUserData(botName=telegram_bot_name)
                            for room, member in members:
                                if member.telegramID is None or len(member.telegramID) < 3:
                                    LOG.debug("Member " + str(member) + " has no known telegramID, skip sending")
                                    continue

                                isSent: bool = self.sendAndSyncWithDatabaseElectionIsComing(member=member,
                                                                                            election=election,
                                                                                            reminder=reminder,
                                                                                            reminderSentList=reminderSentList)
                                if isSent:
                                    LOG.info("Reminder (for user: " + member.accountName + " sent to telegramID: "
                                             + member.telegramID)

                        else:
                            LOG.debug("... reminder is not needed!")

            else:
                LOG.error("Reminders are not set in the database. Something went wrong.")
        except Exception as e:
            LOG.exception("Exception thrown when called sendReminderIfNeeded; Description: " + str(e))

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

    def getMembersFromDatabaseInElection(self, election: Election, reminder: Reminder):
        """Get participants from database in election process"""
        """Returns list of rooms[0] and participants[1]"""
        try:
            assert isinstance(election, Election), "election is not instance of Election"
            assert isinstance(reminder, Reminder), "reminder is not instance of Reminder"

            # round is in the reminder object
            LOG.info("Get participants from database in election process")
            groupsAndParticipants = self.database.getMembersInElectionRoundNotYetSend(election=election,
                                                                                      reminder=reminder)
            return groupsAndParticipants
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
            raise ReminderManagementException("Exception thrown when called nearestDateTime; Description: " + str(e))

    def getTextForUpcomingElection(self, member: Participant, electionDateTime: datetime, reminder: Reminder,
                                   currentTime: datetime) -> str:
        try:
            LOG.info("Getting text for election: " + str(electionDateTime))

            assert isinstance(electionDateTime, datetime), "electionDateTime is not instance of datetime"
            assert isinstance(currentTime, datetime), "currentTime is not instance of datetime"
            assert isinstance(reminder, Reminder), "reminder is not instance of Reminder"
            assert isinstance(member, Participant), "member is not instance of Participant"

            # get timedifference in text format from constants
            minutesToElectionInMinutes = (electionDateTime - currentTime).total_seconds() / 60
            nearestDatetimeToElectionInMinutes: tuple[int, ReminderGroup, str] = \
                self.theNearestDateTime(alert_message_time_election_is_coming, minutesToElectionInMinutes)
            nearestDateTimeText = nearestDatetimeToElectionInMinutes[2]
            LOG.debug("Nearest datetime to election: " + str(nearestDatetimeToElectionInMinutes) +
                      " minutes with text '" + nearestDateTimeText + "'")

            if member.participationStatus and \
                    (nearestDatetimeToElectionInMinutes[1] == ReminderGroup.BOTH or
                     nearestDatetimeToElectionInMinutes[1] == ReminderGroup.ATTENDED):
                LOG.debug("Member (" + str(member) + ") is going to participate and reminder is for 'attended members'")
                return _("Hey! \n"
                         "I am here to remind you that Eden election is starting %s.") % \
                       (nearestDateTimeText)

            elif member.participationStatus is False and \
                    (nearestDatetimeToElectionInMinutes[1] is ReminderGroup.BOTH or \
                     nearestDatetimeToElectionInMinutes[1] is ReminderGroup.NOT_ATTENDED):
                LOG.debug("Member (" + str(member) + ") is not going to participate and reminder "
                                                     "is for 'not attended members'")
                return _("Hey! \n"
                         "I am here to remind you that Eden election is starting %s."
                         " \n You are not attending this election, so you will not be able to participate.\n\n"
                         "You can change your attendance status by pressing the button below text:.") % \
                       (nearestDateTimeText)
            else:
                LOG.debug("Do not send reminder to member (" + str(member) + ").")
                return ""
        except Exception as e:
            LOG.exception("Exception in getTextForUpcomingElection: " + str(e))
            raise ReminderManagementException("Exception in getTextForUpcomingElection: " + str(e))

    def sendToTheGroupTimeIsUp(self,
                               election: Election,
                               reminderRound: int,
                               closestReminderConst: tuple[int, ReminderGroup, str],
                               roomArray: RoomArray,
                               modeDemo: ModeDemo = None):
        """Send reminder that the round is almost finished - in group"""
        try:
            assert isinstance(election, Election), "election is not instance of Election"
            assert isinstance(reminderRound, int), "reminderRound is not instance of int"
            assert isinstance(closestReminderConst, tuple), "closestReminderConst is not instance of tuple"
            assert isinstance(roomArray, RoomArray), "roomArray is not instance of RoomArray"
            assert isinstance(modeDemo, ModeDemo), "modeDemo is not instance of ModeDemo"

            gctm: GroupCommunicationTextManagement = GroupCommunicationTextManagement()
            timeIsUpButtons: tuple[str] = gctm.timeIsAlmostUpButtons()

            # prepare replay markup
            replyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                [
                    [  # First row - link to the portal
                        InlineKeyboardButton(  # Opens a web URL
                            timeIsUpButtons[0],
                            url=eden_portal_url_action
                        )
                    ]
                ]
            )

            LOG.info("Send reminder that the round is almost finished - in group")
            rooms: list[ExtendedRoom] = roomArray.getRoomArray()
            self.communication.updateKnownUserData(botName=telegram_bot_name)
            for room in rooms:
                try:
                    # prepare and sent message to the group
                    text: str = gctm.timeIsAlmostUpGroup(timeLeftInMinutes=closestReminderConst[0],
                                                         round=reminderRound,
                                                         extendedRoom=room,
                                                         )

                    if room.roomTelegramID is None:
                        LOG.error("ReminderManagement.sendToTheGroupTimeIsUp; Room telegram ID is None")
                        raise ReminderManagementException(
                            "ReminderManagement.sendToTheGroupTimeIsUp;Room telegram ID is None")

                    sendResponse = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                                  chatId=int(room.roomTelegramID),
                                                                  text=text,
                                                                  inlineReplyMarkup=replyMarkup)

                    if sendResponse is not None:
                        LOG.debug("sendToTheGroupTimeIsUp; Message was sent to the group: " + str(room.roomTelegramID))
                    else:
                        LOG.error(
                            "sendToTheGroupTimeIsUp; Message was not sent to the group: " + str(room.roomTelegramID))
                except:
                    LOG.exception("Exception thrown when called sendToTheGroupTimeIsUp; Description: ")



        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException("Exception thrown when called sendToTheGroup; Description: " + str(e))

    def sendAndSyncWithDatabaseRoundIsAlmostFinish(self, member: ExtendedParticipant, election: Election,
                                                   reminder: Reminder,
                                                   closestReminderConst: tuple[int, ReminderGroup, str],
                                                   modeDemo: ModeDemo = None) -> bool:
        """Send reminder and write to database"""
        ###I have participants without reminderSent record, send the message to them, write to database

        try:
            assert isinstance(member, ExtendedParticipant), "member is not instance of ExtendedParticipant"
            assert isinstance(election, Election), "election is not instance of Election"
            assert len(closestReminderConst) == 3, "closestReminderConst is not correct size"
            assert isinstance(closestReminderConst[0], int), "closestReminderConst[0] is not instance of int"
            assert isinstance(closestReminderConst[1],
                              ReminderGroup), "closestReminderConst[1] is not instance of ReminderGroup"
            assert isinstance(closestReminderConst[2], str), "closestReminderConst[2] is not instance of str"
            LOG.debug("Member: " + str(member))
            LOG.debug("Election id: " + str(election.electionID))
            LOG.debug("Reminder: " + str(reminder))

            #
            # Create inline keyboard markup
            #
            gctm: GroupCommunicationTextManagement = GroupCommunicationTextManagement()
            timeIsUpButtons: tuple[str] = gctm.timeIsAlmostUpButtons()

            if len(timeIsUpButtons) != 2:
                LOG.exception("timeIsUpButtons is not tuple with 2 items")
                raise ReminderManagementException("timeIsUpButtons is not tuple with 2 items")

            replyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                [
                    [  # First row - link to the portal
                        InlineKeyboardButton(  # Opens a web URL
                            timeIsUpButtons[0],
                            url=eden_portal_url_action
                        ),
                        # Second row - link to the blocks
                        InlineKeyboardButton(  # Opens a web URL
                            timeIsUpButtons[1],
                            url=RawActionWeb().electVote(round=reminder.round,
                                                         voter=member.accountName,
                                                         candidate=None)
                        ),
                    ]
                ]
            )

            #
            # Send message to the user
            #

            # prepare and send notification to the user
            text: str = gctm.timeIsAlmostUpPrivate(timeLeftInMinutes=closestReminderConst[0],
                                                   round=reminder.round,
                                                   voteFor=member.voteFor)

            sendResponse: bool = False

            try:
                # LIVE MODE
                cSession = self.database.createCsesion(expireOnCommit=False)
                LOG.trace("Live mode is enabled, sending message to: " + member.telegramID)
                member.telegramID = ADD_AT_SIGN_IF_NOT_EXISTS(member.telegramID)
                sendResponse = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                              chatId=member.telegramID,
                                                              text=text,
                                                              inlineReplyMarkup=replyMarkup)


                # Save the recod to the database
                response = self.database.createOrUpdateReminderSentRecord(reminder=reminder,
                                                               accountName=member.accountName,
                                                               sendStatus=ReminderSendStatus.SEND if sendResponse is True
                                                               else ReminderSendStatus.ERROR,
                                                               cSession=cSession)
                if response is True:
                    self.database.commitCcession(session=cSession)
                else:
                    self.database.rollbackCcession(session=cSession)


                LOG.info("LiveMode; Is message sent successfully to " + member.telegramID + ": " + str(sendResponse)
                         + ". Saving to the database under electionID: " + str(election.electionID))
                self.database.removeCcession(session=cSession)
            except Exception as e:
                LOG.exception("Exception in sendAndSyncWithDatabaseElectionIsComing. Description: " + str(e))
                self.database.rollbackCcession(session=cSession)
                self.database.removeCcession(session=cSession)
            return sendResponse
        except Exception as e:
            LOG.exception("Exception thrown when called sendAndSyncWithDatabaseElectionIsComing; Description: " + str(e))


    def sendAndSyncWithDatabaseElectionIsComing(self, member: Participant, election: Election, reminder: Reminder,
                                                reminderSentList: list[ReminderSent]) -> bool:
        """Send reminder and write to database"""
        try:
            assert isinstance(member, Participant), "member is not instance of Participant"
            assert isinstance(election, Election), "election is not instance of Election"
            assert isinstance(reminder, Reminder), "reminder is not instance of Reminder"
            assert isinstance(reminderSentList, list), "reminderSentList is not instance of list"
            LOG.trace("Send and sync with database: election is coming; "
                      "Member: " + str(member) +
                      ", Election: " + str(election) +
                      ", Reminder: " + str(reminder))

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

            sendResponse: bool = False

            try:
                cSession = self.database.createCsesion(expireOnCommit=False)
                LOG.trace("Live mode is enabled, sending message to: " + member.telegramID)
                member.telegramID = ADD_AT_SIGN_IF_NOT_EXISTS(member.telegramID)
                sendResponse = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                              chatId=member.telegramID,
                                                              text=text,
                                                              inlineReplyMarkup=replyMarkup)

                LOG.info("LiveMode; Is message sent successfully to " + member.telegramID + ": " + str(sendResponse)
                         + ". Saving to the database under electionID: " + str(election.electionID))

                response: bool = self.database.createOrUpdateReminderSentRecord(reminder=reminder, accountName=member.accountName,
                                                               sendStatus=ReminderSendStatus.SEND if sendResponse is True
                                                               else ReminderSendStatus.ERROR,
                                                               cSession=cSession)
                if response is True:
                    self.database.commitCcession(session=cSession)
                else:
                    self.database.rollbackCcession(session=cSession)
                self.database.removeCcession(session=cSession)
            except Exception as e:
                LOG.exception("Exception in sendAndSyncWithDatabaseElectionIsComing. Description: " + str(e))
                self.database.rollbackCcession(session=cSession)
                self.database.removeCcession(session=cSession)
            return sendResponse

        except Exception as e:
            LOG.exception("Exception thrown when called sendAndSyncWithDatabaseElectionIsComing; Description: " + str(e))