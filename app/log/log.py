# pip install loguru

from loguru import logger

class Log:

    def __init__(self, className: str):
        self.className = className

    def sendLogToAdmin(self, level: str, log: str):
        kva = 9

    @staticmethod
    def trace(message: str):
        logger.trace(message)

    def trace(self, message: str):
        logger.trace(message)
        self.sendLogToAdmin("Trace", message)

    @staticmethod
    def debug(message: str):
        logger.debug(message)

    def debug(self, message: str):
        logger.debug(message)
        self.sendLogToAdmin("Debug", message)

    @staticmethod
    def info(message: str):
        logger.info(message)

    def info(self, message: str):
        logger.info(message)
        self.sendLogToAdmin("Info", message)

    @staticmethod
    def success(message: str):
        logger.success(message)

    def success(self, message: str):
        logger.success(message)
        self.sendLogToAdmin("Success", message)

    @staticmethod
    def warning(message: str):
        logger.warning(message)

    def warning(self, message: str):
        logger.warning(message)
        self.sendLogToAdmin("Warnings", message)

    @staticmethod
    def error(message: str):
        logger.error(message)

    def error(self, message: str):
        logger.error(message)
        self.sendLogToAdmin("Error", message)

    @staticmethod
    def critical(message: str):
        logger.critical(message)

    def critical(self, message: str):
        logger.critical(message)
        self.sendLogToAdmin("Critical", message)

    @staticmethod
    def exception(message: str):
        logger.exception(message)

    def exception(self, message: str):
        logger.exception(message)
        self.sendLogToAdmin("Exception", message)



