import datetime as DateTimeP

from sqlalchemy import DateTime, MetaData, Table, Column, Text, CHAR, VARBINARY, VARCHAR, String
from database.base import Base

class Abi(Base):
    __tablename__ = 'abi'
    accountName = Column(CHAR(32), primary_key=True)
    lastUpdate = Column(DateTime, nullable=False)
    contract = Column(Text, nullable=False)

    """Class for interaction between code structure and database"""
    #accountName: str
    #lastUpdate: DateTimeP
    #contract: bytes

    #@staticmethod
    """def createTable(meta: MetaData):
        return Table(
            'abi', meta,
            Column('accountName', VARCHAR(16), primary_key=True),
            Column('lastUpdate', DateTime),
            Column('contract', VARBINARY(16384))
        )"""

    def __init__(self, accountName: str, contract: String, lastUpdate: DateTime = DateTimeP.datetime.utcnow()):
        """Initialization object"""
        self.accountName = accountName
        self.lastUpdate = lastUpdate
        self.contract = contract




