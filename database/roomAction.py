from enum import Enum
from datetime import datetime
from sqlalchemy import DateTime, Column, Integer, ForeignKey, Text

from database.room import Room
from database.base import Base


class RoomActionType(Enum):
    """Enum to specify action in room"""
    STARTED_VIDEO = 0
    ENDED_VIDE0 = 1

class RoomAction(Base):
    __tablename__ = 'roomAction'
    """Class for interaction between code structure and database"""
    roomActionID = Column(Integer, primary_key=True, autoincrement=True)
    roomID = Column(Integer, ForeignKey(Room.roomID), nullable=False)
    dateTime = Column(DateTime, nullable=False)
    actionType = Column(Integer, nullable=False)
    additionalData = Column(Text)

    def __init__(self, roomID: int, dateTime: datetime, actionType: RoomActionType, additionalData: str = None,
                 roomActionID: int = None):
        """Initialization object"""
        assert isinstance(roomID, int), "RoomID must be int"
        assert isinstance(dateTime, datetime), "DateTime must be datetime"
        assert isinstance(actionType, RoomActionType), "ActionType must be RoomActionType"
        assert isinstance(additionalData, (str, type(None))), "AdditionalData must be str or None"
        assert isinstance(roomActionID, (int, type(None))), "RoomActionID must be int or None"

        self.roomActionID = roomActionID
        self.roomID = roomID
        self.dateTime = dateTime
        self.actionType = actionType.value
        self.additionalData = additionalData

    def __str__(self):
        return f"RoomActionID: {self.roomActionID}, " \
               f"RoomID: {self.roomID}, " \
               f"DateTime: {self.dateTime}, " \
               f"ActionType: {self.actionType}, " \
               f"AdditionalData: {self.additionalData}"
