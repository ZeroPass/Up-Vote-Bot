import logging
import time
from datetime import datetime, timedelta
from log import Log
from enum import Enum
from chain import EdenData


class Mode(Enum):
    DEMO = 1,
    LIVE = 2,


class ModeDemoException(Exception):
    pass


LOG = Log(className="ModeDemo")


class ModeDemo:
    currentBlockHeight: int = None
    currentBlockTimestamp: datetime = None

    """Store the time of start and end of the election"""

    def __init__(self, startAndEndDatetime: list[tuple[datetime, datetime]], edenObj: EdenData, step: int = 1,
                 fromLive: bool = False):
        #step is import only if you call getNextBlock(), not setNextTimestamp()
        # Example 1 - with block height:
        # if isNextBlock():
        #    getNextBlock()

        # Example 2 - with timestamp:
        # if isNextTimestampInLimit(nextTimestamp=nextTimestamp):
        #    setNextTimestamp(nextTimestamp=nextTimestamp)



        LOG.debug("Initialization of ModeDemo with startAndEndDatetime: " + str(startAndEndDatetime) +
                          " and step: " + str(step))
        assert isinstance(startAndEndDatetime, list), "Start is not a list object"
        assert isinstance(edenObj, EdenData), "EdenObj is not a EdenData object"
        assert isinstance(step, int), "Step is not an integer"

        if step < 1:
            LOG.exception("ModeDemo; Step must be greater than 0")
            raise ModeDemoException("Step must be greater than 0")

        LOG.debug("Checking datetime list of tuples")
        for oneTimeFrame in startAndEndDatetime:
            if oneTimeFrame[0] > oneTimeFrame[1]:
                LOG.exception("ModeDemo; Start is greater than end")
                raise ModeDemoException("Start is greater than end")
            if isinstance(oneTimeFrame[0], datetime) is False:
                LOG.exception("ModeDemo; Start is not a datetime object")
                raise ModeDemoException("Start is not a datetime object")
            if isinstance(oneTimeFrame[1], datetime) is False:
                LOG.exception("ModeDemo; End is not a datetime object")
                raise ModeDemoException("End is not a datetime object")
        if fromLive is False:
            self.edenObj = edenObj
            self.liveMode = False
            self.startAndEndDatetime = startAndEndDatetime
            self.currentTimeFrameIndex = 0
            self.currentBlockTimestamp = self.startAndEndDatetime[self.currentTimeFrameIndex][0]
            self.setNextTimestamp(seconds=0)

            self.step = step

    """ModeDemo has 2 mode. One is in the past when you create set of bloks. You can call it by constcutor.
       Other mode is (half)LIVE but few blocks back (stepBack). You can call it by call constcutror live(...)
        Whey you use second mode you can step forward by calling setNextLiveBlockAndTimestamp.
        You can check in what mode is the ModeDemo instance by calling function isLive()
    """
    @classmethod
    def live(cls, edenObj: EdenData, stepBack: int):
        assert isinstance(edenObj, EdenData), "EdenObj is not a EdenData object"
        assert isinstance(stepBack, int), "Step is not an integer"
        if stepBack < 1:
            LOG.exception("ModeDemo; stepBack must be greater than 0")
            raise ModeDemoException("StepBack must be greater than 0")
        LOG.debug("Live mode activated")

        cls.liveMode = True
        #selfObject = cls(edenObj=edenObj,
        #    startAndEndDatetime=[(datetime(2022, 10, 8, 14, 59), datetime(2022, 10, 8, 15, 3))])

        cls.edenObj = edenObj
        cls.stepBack = stepBack
        cls.currentBlockHeight = cls.edenObj.getChainHeadBlockNumber() - cls.stepBack
        cls.currentBlockTimestamp = cls.edenObj.getTimestampOfBlock(blockNum=cls.currentBlockHeight)
        return cls(edenObj=edenObj,
                   startAndEndDatetime=[(datetime(2022, 10, 8, 14, 59), datetime(2022, 10, 8, 15, 3))],
                   fromLive = True)



    def isLiveMode(self) -> bool:
        return self.liveMode

    #works only when demoMode is called by DemoMode.live(...)
    def setNextLiveBlockAndTimestamp(self):
        assert (self.liveMode is True), "LiveMode should be True when you call 'ModeDemo.setNextLiveBlockAndTimestamp'"
        self.currentBlockHeight = self.edenObj.getChainHeadBlockNumber() - self.stepBack
        self.currentBlockTimestamp = self.edenObj.getTimestampOfBlock(blockNum=self.currentBlockHeight)
        LOG.debug("Block: " + str(self.currentBlockHeight) + ", timestamp" + str(self.currentBlockTimestamp))

    def setStartBlockHeight(self, height: int):
        assert isinstance(height, int), "Height is not an integer"
        LOG.debug("ModeDemo; Set start block height to: " + str(height))
        self.startBlockHeight = height
        self.currentBlockHeight = height
        self.currentBlockTimestamp = self.edenObj.getTimestampOfBlock(blockNum=height)

    def setEndBlockHeight(self, height: int):
        assert isinstance(height, int), "Height is not an integer"
        LOG.debug("ModeDemo; Set end block height to: " + str(height))
        self.endBlockHeight = height

    def isNextTimestampInLimit(self, seconds: int) -> bool:
        assert isinstance(seconds, int), "seconds is not a int object"
        if self.currentBlockTimestamp + timedelta(seconds=seconds) <= \
                       self.startAndEndDatetime[self.currentTimeFrameIndex][1]\
                or \
           self.currentTimeFrameIndex + 1 < len(self.startAndEndDatetime): #second condition if there is a next time frame
            return True
        else:
            return False

    def setNextTimestamp(self, seconds: int):
        assert isinstance(seconds, int), "seconds is not a int object"
        if self.currentBlockTimestamp + timedelta(seconds=seconds) <= \
                self.startAndEndDatetime[self.currentTimeFrameIndex][1]:
            self.currentBlockTimestamp = self.currentBlockTimestamp + timedelta(seconds=seconds)
            LOG.success("ModeDemo; Set next timestamp to: " + str(self.currentBlockTimestamp))
        else:
            self.currentTimeFrameIndex = self.currentTimeFrameIndex + 1
            self.currentBlockTimestamp = self.startAndEndDatetime[self.currentTimeFrameIndex][0]
            LOG.success("ModeDemo; Set next timestamp and sector to: " + str(self.currentBlockTimestamp))
            LOG.success("Lets wait 3 minutes for new sector")
            time.sleep(120)
        try:
            self.currentBlockHeight = self.edenObj.getBlockNumOfTimestamp(timestamp=self.currentBlockTimestamp).data
        except Exception as e:
            LOG.exception("ModeDemo; Exception: " + str(e))
            raise ModeDemoException("Exception: " + str(e))

    def isNextBlock(self):
        if self.currentBlockHeight is None:
            LOG.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        return True if self.currentBlockHeight + self.step <= self.endBlockHeight else False

    def getNextBlock(self):
        if self.currentBlockHeight is None:
            LOG.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        self.currentBlockHeight += self.step
        self.currentBlockTimestamp = self.edenObj.getTimestampOfBlock(blockNum=self.currentBlockHeight)
        LOG.debug("ModeDemo; Current block height is now: " + str(self.currentBlockHeight) +
                          " and timestamp is: " + str(self.currentBlockTimestamp))
        if self.isNextBlock() is False:
            LOG.exception("ModeDemo; Next block is not available")
            raise ModeDemoException("No next block available")
        return self.currentBlockHeight

    def getCurrentBlock(self) -> int:
        if self.currentBlockHeight is None:
            LOG.exception("ModeDemo; Current block is not available")
            raise ModeDemoException("No current block available")
        return self.currentBlockHeight

    def getCurrentBlockTimestamp(self) -> datetime:
        if self.currentBlockTimestamp is None:
            LOG.exception("ModeDemo; Current block timestamp is not available")
            raise ModeDemoException("No current block timestamp available")
        return self.currentBlockTimestamp


