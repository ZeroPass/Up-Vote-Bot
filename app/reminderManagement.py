from app.chain.dfuse import DfuseConnection
from app.constants import dfuse_api_key
from app.database import Election, Database
from app.log import Log
from datetime import datetime, timedelta
from app.chain.eden import EdenData, Response, ResponseError
from app.database.participant import Participant
from app.database.reminder import Reminder
from datetime import datetime
from app.debugMode.modeDemo import ModeDemo
from app.dateTimeManagement import DateTimeManagement


class ReminderManagementException(Exception):
    pass


LOG = Log(className="ParticipantsManagement")


class ReminderManagement:

    def __init__(self, edenData: EdenData, dateTimeManagement: DateTimeManagement):
        self.edenData = edenData
        self.dateTimeManagement = dateTimeManagement
        self.participants = []

    def createReminder(self, election: Election, height: int = None):
        """Create reminder"""
        try:
            LOG.info("Create reminders")
            database: Database = Database()
            database.createRemindersIfNotExists(election=election)
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
            blockchainTime: datetime = modeDemo.getExecutionTime()
            return blockchainTime

    def sendReminderIfNeeded(self, election: Election, modeDemo: ModeDemo = None):
        """Send reminder if needed"""
        try:
            LOG.info("Send reminders if needed")

            database: Database = Database()
            workingTime = self.setExecutionTime(modeDemo=modeDemo)
            LOG.debug("Working time: " + str(workingTime))

            reminders = database.getReminders(election=election)
            if reminders is not None:
                for item in reminders:
                    if isinstance(item, Reminder):
                        reminder: Reminder = item
                        LOG.info("Reminder: " + str(reminder))

                        if reminder.dateTimeBefore < workingTime < reminder.dateTimeBefore + timedelta(
                                minutes=5):
                            LOG.info("Send reminder to: " + str(reminder.telegramID))

            else:
                LOG.error("Reminders are not set in the database. Something went wrong.")
        except Exception as e:
            LOG.exception(str(e))
            raise ReminderManagementException(
                "Exception thrown when called sendReminderIfNeeded; Description: " + str(e))

    def getMembersFromChain(self, height: int = None):
        """Get participants from chain"""
