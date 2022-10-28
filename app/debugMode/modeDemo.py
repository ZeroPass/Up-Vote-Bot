from datetime import datetime
from app.log import Log
from enum import Enum
from app.chain import EdenData



class Mode(Enum):
    DEMO = 1,
    LIVE = 2,

class ModeDemoException(Exception):
    pass

LOGModeDemo = Log(className="ModeDemo")

class ModeDemo:
    currentBlockHeight: int = None
    currentBlockTimestamp: datetime = None

    """Store the time of start and end of the election"""

    def __init__(self, start: datetime, end: datetime, edenObj: EdenData):
        LOGModeDemo.debug("Initialization of ModeDemo with start: " + str(start) + " and end: " + str(end))
        self.startDT = start
        self.endDT = end
        self.edenObj = edenObj

    def getStart(self) -> datetime:
        return self.startDT

    def getEnd(self) -> datetime:
        return self.endDT

    def setStartBlockHeight(self, height: int):
        LOGModeDemo.debug("ModeDemo; Set start block height to: " + str(height))
        self.startBlockHeight = height
        self.currentBlockHeight = height
        self.currentBlockTimestamp = self.edenObj.getTimestampOfBlock(height)

    def setEndBlockHeight(self, height: int):
        LOGModeDemo.debug("ModeDemo; Set end block height to: " + str(height))
        self.endBlockHeight = height

    def isNextBlock(self):
        if self.currentBlockHeight is None:
            LOGModeDemo.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        return True if self.currentBlockHeight + 1 <= self.endBlockHeight else False

    def getNextBlock(self):
        if self.currentBlockHeight is None:
            LOGModeDemo.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        self.currentBlockHeight += 1
        self.currentBlockTimestamp = self.edenObj.getBlockNumOfTimestamp(timestamp=self.currentBlockHeight)
        if self.isNextBlock() is False:
            LOGModeDemo.exception("ModeDemo; Next block is not available")
            raise ModeDemoException("No next block available")
        return self.currentBlockHeight

    def getCurrentBlock(self):
        if self.currentBlockHeight is None:
            LOGModeDemo.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        return self.currentBlockHeight

    def getCurrentBlockTimestamp(self):
        if self.currentBlockTimestamp is None:
            LOGModeDemo.exception("ModeDemo; Current block timestamp is not available")
            raise ModeDemoException("No current block timestamp available")
        return self.currentBlockTimestamp