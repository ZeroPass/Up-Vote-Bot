import datetime as DateTimeP

from sqlalchemy import DateTime, MetaData, Table, Column, Text, CHAR, VARBINARY, VARCHAR, String, Integer
from app.database.base import Base

class Token(Base):
    __tablename__ = 'token'
    name = Column(CHAR(32), nullable=False, primary_key=True)
    value = Column(Text, nullable=False)
    expireBy = Column(DateTime, nullable=False)


    def __init__(self, name: str, value: str, expireBy: DateTime):
        """Initialization object"""
        self.name = name
        self.value = value
        self.expireBy = expireBy




