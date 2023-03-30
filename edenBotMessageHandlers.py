import time
from chain.electionStateObjects import EdenBotMode
from constants import dfuse_api_key, telegram_api_id, telegram_api_hash, telegram_bot_token, CurrentElectionState
from database import Database
from log import Log

from transmission import Communication

class EdenBotException(Exception):
    pass


LOG = Log(className="EdenBotMessageHandler")

#TODO: in the future move message handlers to this class
class EdenBotMessageHandler:
    botMode: EdenBotMode

    def __init__(self, telegramApiID: int, telegramApiHash: str, botToken: str, database: Database):
        LOG.info("Initialization of EdenBotMessageHandler")
        assert isinstance(telegramApiID, int), "telegramApiID is not an integer"
        assert isinstance(telegramApiHash, str), "telegramApiHash is not a string"
        assert isinstance(botToken, str), "botToken is not a string"
        assert isinstance(database, Database), "database is not an instance of Database"

        self.database = database
        self.communication = Communication(database=database)
        self.communication.startSessionAsync(apiId=telegramApiID,
                                            apiHash=telegramApiHash,
                                            botToken=botToken)

def main():
    print("------>Python<-------")
    import sys
    print("\nVersion: " + str(sys.version))
    print("\n\n")
    print("------>EdenBot (Message Handler) Support<-------\n\n")

    database = Database()
    EdenBotMessageHandler(telegramApiID=telegram_api_id,
                          telegramApiHash=telegram_api_hash,
                          botToken=telegram_bot_token,
                          database=database).start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
