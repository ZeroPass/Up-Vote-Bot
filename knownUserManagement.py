from datetime import datetime

from chain import EdenData
from database import Database, KnownUser
from dateTimeManagement import DateTimeManagement
from debugMode.modeDemo import ModeDemo
from log import Log
from transmission import Communication
from transmission.name import REMOVE_AT_SIGN_IF_EXISTS


class KnownUserManagementException(Exception):
    pass

class KnownUserDataException(Exception):
    pass

LOG = Log(className="KnownUserManagement")
LOGkud= Log(className="KnownUserData")

class KnownUserData:
    def __init__(self, database: Database):
        assert isinstance(database, Database), "database is not a Database object"
        self.database = database
        self.knownUsers = None

    def removeAtSignAtBeginning(self, telegramID: (str, int)) -> (str, int):
        assert isinstance(telegramID, (str, int)), "telegramID is not a string or int"
        return REMOVE_AT_SIGN_IF_EXISTS(name=telegramID)

    def setKnownUser(self, botName: str, telegramID: (str, int), isKnown: bool) -> bool:
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(telegramID, (str, int)), "telegramID is not a string or int"
        assert isinstance(isKnown, bool), "isKnown is not a boolean"
        try:
            telegramID = self.removeAtSignAtBeginning(telegramID=telegramID)
            isSetted: bool = self.database.setKnownUser(botName=botName, telegramID=str(telegramID), isKnown=isKnown)
            self.getKnownUsersOptimizedSave(botName=botName)
            return isSetted
        except Exception as e:
            LOGkud.exception("Set known user failed with error" + str(e))
            return False

    def removeKnownUser(self, botName: str, telegramID: (str, int)) -> bool:
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(telegramID, (str, int)), "telegramID is not a string or int"
        try:
            telegramID = self.removeAtSignAtBeginning(telegramID=telegramID)
            self.database.setKnownUser(botName=botName, telegramID=telegramID, isKnown=False)
            self.getKnownUsersOptimizedSave(botName=botName)
            return True
        except Exception as e:
            LOGkud.exception("Set known user failed with error" + str(e))
            return False

    def getKnownUser(self, botName: str, telegramID: (str, int)) -> KnownUser:
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(telegramID, (str, int)), "telegramID is not a string or int"
        try:
            telegramID = self.removeAtSignAtBeginning(telegramID=telegramID)
            return self.database.getKnownUser(botName=botName, telegramID=telegramID)
        except Exception as e:
            LOGkud.exception("Get known user failed with error" + str(e))
            return None

    def getKnownUsers(self, botName: str) -> [KnownUser]:
        try:
            assert isinstance(botName, str), "botName is not a string"
            return self.database.getKnownUsers(botName=botName)
        except Exception as e:
            LOGkud.exception("Get known users failed with error" + str(e))
            return []

    def getKnownUsersOptimizedSave(self, botName: str) -> bool:
        assert isinstance(botName, str), "botName is not a string"
        try:
            self.knownUsers = self.database.getKnownUsers(botName=botName)
            return True
        except Exception as e:
            LOGkud.exception("Get known users optimized save failed with error" + str(e))
            return False

    def getKnownUserFromOptimized(self, botName: str, telegramID: (str, int)) -> KnownUser:
        assert isinstance(botName, str), "botName is not a string"
        assert isinstance(telegramID, (str, int)), "telegramID is not a string or int"
        try:
            telegramID = self.removeAtSignAtBeginning(telegramID=telegramID)
            if self.knownUsers is None:
                LOGkud.error("Known users are not loaded - please call getKnownUsersOptimizedSave first - because"
                             "of performance reasons")
                self.getKnownUsersOptimizedSave(botName=botName)
            for knownUser in self.knownUsers:
                if knownUser.userID.lower() == telegramID.lower():
                    return knownUser
            return None #return None if not found
        except Exception as e:
            LOGkud.exception("Get known user from optimized failed with error" + str(e))
            return None

    def getKnownUsersOptimizedOnlyBoolean(self, botName: str, telegramID: str) -> bool:
        assert isinstance(botName, str), "botName is not a string"
        try:
            telegramID = self.removeAtSignAtBeginning(telegramID=telegramID)
            knownUser: KnownUser = self.getKnownUserFromOptimized(botName=botName, telegramID=telegramID)
            if knownUser is None:
                return False
            if isinstance(knownUser, KnownUser):
                return knownUser.isKnown
            return False
        except Exception as e:
            LOGkud.exception("Get known users optimized failed with error" + str(e))
            return []



class KnownUserManagement:

    def __init__(self, database: Database, edenData: EdenData):
        assert isinstance(database, Database), "database is not a Database object"
        assert isinstance(edenData, EdenData), "edenData is not a EdenData object"

        self.dateTimeManagement = DateTimeManagement(edenData=edenData)
        self.database = database

    def setExecutionTime(self) -> datetime:
            # in live mode time of blockchain is also time of server
            blockchainTime: datetime = self.dateTimeManagement.getTime()
            return blockchainTime

    def getUpdatesIfNeeded(self):
        # get updates from telegram
        kva = 9
