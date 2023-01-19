from datetime import datetime

from sqlalchemy import DateTime, Column, Text, CHAR
from database.base import Base

class TokenService(Base):
    __tablename__ = 'tokenService'
    name = Column(CHAR(32), nullable=False, primary_key=True)
    value = Column(Text, nullable=False)
    expireBy = Column(DateTime, nullable=False)


    def __init__(self, name: str, value: str, expireBy: datetime):
        """Initialization object"""
        self.name = name
        self.value = value
        self.expireBy = expireBy




