from datetime import datetime
import time

from pyrogram.raw.base import ReplyMarkup
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from twisted.web.http import responses

from app.constants import CurrentElectionState
from app.database.participant import Participant
from app.debugMode.modeDemo import Mode
from app.log import Log
from app.database import Database, Election, ExtendedRoom, Reminder, ElectionStatus, ReminderSendStatus
from app.transmission import Communication, SessionType, Communication
from app.constants.parameters import alert_message_time_election_is_coming, alert_message_time_election_is_coming_text, \
    telegram_api_id, telegram_api_hash, telegram_bot_token, eden_portal_url, telegram_admins_id

import gettext

_ = gettext.gettext
__ = gettext.ngettext

from app.dateTimeManagement import DateTimeManagement


class TransmissionManagementException(Exception):
    pass


LOG = Log(className="TransmissionManagement")


class GroupName:
    # Eden R1G1 Delegates S4,2022
    # Eden - Round 1, Group 1, Delegates. Season 4, Year 2022.

    # and
    # Eden Chief Delegates S4,2022
    # Eden Chief Delegates. Season 4, Year 2022.

    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name


class TransmissionManagement:
    def __init__(self, communication: Communication, mode: Mode):
        assert (communication is not None), "Communication should not be null"
        assert (mode is not None), "Mode should not be null"
        if not communication.isInitialized:
            raise TransmissionManagementException("Communication is not initialized")
        self.communication: Communication = communication
        self.mode: Mode = mode

    def createGroup(self, name: str, participants: list) -> int:
        LOG.info("Creating group: " + name + " with participants: " + str(participants))
        try:
            assert name is not None, "Name should not be null"
            assert participants is not None, "Participants should not be null"

        except Exception as e:
            LOG.exception("Exception (in createGroup): " + str(e))
            raise TransmissionManagementException("Exception (in createGroup): " + str(e))

    def nearestDateTime(self, items, pivot):
        return min(items, key=lambda x: abs(x - pivot))

    def getTextForUpcomingElection(self, electionDateTime: datetime, currentTime: datetime, isAttended: bool) -> str:
        try:
            LOG.info("Getting text for election: " + str(electionDateTime))

            assert isinstance(electionDateTime, datetime)
            assert isinstance(currentTime, datetime)
            assert isinstance(isAttended, bool)

            # get timedifference in text format from constants
            minutesToElectionInMinutes = (electionDateTime - currentTime).total_seconds() / 60
            nearestDatetimeToElectionInMinutes: int = self.nearestDateTime(alert_message_time_election_is_coming,
                                                                           minutesToElectionInMinutes)
            nearestDateTimeText = alert_message_time_election_is_coming_text[
                alert_message_time_election_is_coming.index(nearestDatetimeToElectionInMinutes)]
            LOG.debug("Nearest datetime to election: " + str(
                nearestDatetimeToElectionInMinutes) + " minutes with text '" + nearestDateTimeText + "'")

            if isAttended:
                return _("Hey! \n"
                         "I am here to remind you that Eden election is starting in %s.") % \
                       (nearestDateTimeText)

            else:
                return _("Hey! \n"
                         "I am here to remind you that Eden election is starting in %s."
                         " \n You are not attending this election, so you will not be able to participate.\n\n"
                         "You can change your attendance status by pressing the button below text:.") % \
                       (nearestDateTimeText)
        except Exception as e:
            LOG.exception("Exception (in getTextForUpcomingElection): " + str(e))
            raise TransmissionManagementException("Exception (in getTextForUpcomingElection): " + str(e))

    def sendAlertForUpcomingElectionInBotChat(self, election: Election, reminder: Reminder,
                                              participants: list[Participant]):
        raise NotImplementedError("Not implemented")
        # participants are stored as list of tuples (username(str), isAttending(bool))
        try:
            assert election is not None, "Election should not be null"
            assert participants is not None, "List of participatns should not be null"
            assert reminder is not None, "Reminder should not be null"
            LOG.info("Sending alert for election: " + election.electionID + " for notification time: "
                     + str(reminder.dateTimeBefore) + " with participants: " + str(participants))

            for item in participants:
                try:
                    if type(item) is not Participant:
                        raise TransmissionManagementException("TransmissionManagement.sendAlertForUpcomingElectionInBotChat; "
                                                              "participant should be of type Participant")

                    text: str = self.getTextForUpcomingElection(election.date, reminder.dateTimeBefore,
                                                                item.participationStatus)

                    replyMarkup: InlineKeyboardMarkup = InlineKeyboardMarkup(
                        [
                            [  # First row
                                InlineKeyboardButton(  # Opens a web URL
                                    "Change the status",
                                    url=eden_portal_url
                                ),
                            ]
                        ]
                    ) if item[1] is False else None


                    # be sure that next comparison is correct, because we really do not want to send fake messages to
                    # users

                    if self.mode == Mode.LIVE:
                        LOG.trace("Live mode is enabled, sending message to: " + item.telegramID)
                        sendResponse: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                                            chatId=item.telegramID,
                                                                            text=text,
                                                                            replyMarkup=replyMarkup)

                        LOG.info("LiveMode; Is message sent successfully to " + item.telegramID + ": " + sendResponse
                                 + ". Saving to the database "
                                 + election.electionID)
                        _database = Database()
                        _database.createReminderSentRecord(reminder=reminder, accountName=item.telegramID,
                                                           sendStatus=ReminderSendStatus.SEND if sendResponse is True
                                                           else ReminderSendStatus.ERROR)

                    else:
                        LOG.trace("Demo mode is enabled, sending message to admins")
                        for admin in telegram_admins_id:
                            text = text + "\n\n" + "Demo mode is enabled, sending message to " + admin
                            sendResponse: bool = self.communication.sendMessage(sessionType=SessionType.BOT,
                                                                                chatId=admin,
                                                                                text=text,
                                                                                replyMarkup=replyMarkup)

                            LOG.info("DemoMode; Is message sent successfully to " + admin + ": " + sendResponse
                                     + ". Saving to the database "
                                     + election.electionID)

                            _database = Database()
                            _database.createReminderSentRecord(reminder=reminder, accountName=item.telegramID,
                                                               sendStatus=ReminderSendStatus.SEND
                                                               if sendResponse is True
                                                               else ReminderSendStatus.ERROR)

                    LOG.debug("Sending to participant: " + item.telegramID + " text: " + text)
                except Exception as eSend:
                    LOG.exception(
                        "Exception (in sendAlertForUpcomingElectionInBotChat.participant loop): " + str(eSend))
        except Exception as e:
            LOG.exception("Exception (in sendAlert): " + str(e))
            raise TransmissionManagementException("Exception (in sendAlertForUpcomingElectionInBotChat): " + str(e))


def main():
    comm = Communication()
    comm.start(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    transmission = TransmissionManagement(communication=comm)
    election = Election(electionID="test",
                        date=datetime(2022, 12, 8, 13),
                        status=ElectionStatus(electionStatusID=4,
                                              status=CurrentElectionState.CURRENT_ELECTION_STATE_ACTIVE))

    transmission.sendAlertForUpcomingElectionInBotChat(election=election,
                                                       reminder=Reminder(dateTimeBefore=datetime.now(),
                                                                         electionID=1),
                                                       participants=[("@nejcskerjanc2", False)])

    print(transmission.getTextForUpcomingElection(electionDateTime=datetime(2022, 10, 8, 13),
                                                  currentTime=datetime.now(), isAttended=False))


if __name__ == "__main__":
    main()
