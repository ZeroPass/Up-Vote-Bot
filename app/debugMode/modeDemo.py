from datetime import datetime, timedelta
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

    def __init__(self, start: datetime, end: datetime, edenObj: EdenData, step: int = 1):
        #step is import only if you call getNextBlock(), not setNextTimestamp()
        # Example 1 - with block height:
        # if isNextBlock():
        #    getNextBlock()

        # Example 2 - with timestamp:
        # if isNextTimestampInLimit(nextTimestamp=nextTimestamp):
        #    setNextTimestamp(nextTimestamp=nextTimestamp)



        LOGModeDemo.debug("Initialization of ModeDemo with start: " + str(start) + " and end: " + str(end)
                          + " and step: " + str(step))
        assert isinstance(start, datetime), "Start is not a datetime object"
        assert isinstance(end, datetime), "End is not a datetime object"
        assert isinstance(edenObj, EdenData), "EdenObj is not a EdenData object"
        assert isinstance(step, int), "Step is not an integer"

        if step < 1:
            LOGModeDemo.exception("ModeDemo; Step must be greater than 0")
            raise ModeDemoException("Step must be greater than 0")
        self.startDT = start
        self.endDT = end
        self.edenObj = edenObj
        self.step = step

    def getStart(self) -> datetime:
        return self.startDT

    def getEnd(self) -> datetime:
        return self.endDT

    def setStartBlockHeight(self, height: int):
        assert isinstance(height, int), "Height is not an integer"
        LOGModeDemo.debug("ModeDemo; Set start block height to: " + str(height))
        self.startBlockHeight = height
        self.currentBlockHeight = height
        self.currentBlockTimestamp = self.edenObj.getTimestampOfBlock(blockNum=height)

    def setEndBlockHeight(self, height: int):
        assert isinstance(height, int), "Height is not an integer"
        LOGModeDemo.debug("ModeDemo; Set end block height to: " + str(height))
        self.endBlockHeight = height

    def isNextTimestampInLimit(self, seconds: int) -> bool:
        assert isinstance(seconds, int), "seconds is not a int object"
        return True if self.currentBlockTimestamp + timedelta(seconds=seconds) <= self.endDT else False

    def setNextTimestamp(self, seconds: int):
        assert isinstance(seconds, int), "seconds is not a int object"
        self.currentBlockTimestamp = self.currentBlockTimestamp + timedelta(seconds=seconds)
        try:
            self.currentBlockHeight = self.edenObj.getBlockNumOfTimestamp(timestamp=self.currentBlockTimestamp).data
        except Exception as e:
            LOGModeDemo.exception("ModeDemo; Exception: " + str(e))
            raise ModeDemoException("Exception: " + str(e))

    def isNextBlock(self):
        if self.currentBlockHeight is None:
            LOGModeDemo.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        return True if self.currentBlockHeight + self.step <= self.endBlockHeight else False

    def getNextBlock(self):
        if self.currentBlockHeight is None:
            LOGModeDemo.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        self.currentBlockHeight += self.step
        self.currentBlockTimestamp = self.edenObj.getTimestampOfBlock(blockNum=self.currentBlockHeight)
        LOGModeDemo.debug("ModeDemo; Current block height is now: " + str(self.currentBlockHeight) +
                          " and timestamp is: " + str(self.currentBlockTimestamp))
        if self.isNextBlock() is False:
            LOGModeDemo.exception("ModeDemo; Next block is not available")
            raise ModeDemoException("No next block available")
        return self.currentBlockHeight

    def getCurrentBlock(self) -> int:
        if self.currentBlockHeight is None:
            LOGModeDemo.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        return self.currentBlockHeight

    def getCurrentBlockTimestamp(self) -> datetime:
        if self.currentBlockTimestamp is None:
            LOGModeDemo.exception("ModeDemo; Current block timestamp is not available")
            raise ModeDemoException("No current block timestamp available")
        return self.currentBlockTimestamp
