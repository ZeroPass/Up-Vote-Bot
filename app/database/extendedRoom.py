from app.database.room import Room
from app.database.extendedParticipant import ExtendedParticipant


class ExtendedRoom(Room):
    def __init__(self, electionID: int, round: int, roomIndex: int, roomNameShort: str, roomNameLong: str,
                 roomID: int = None, roomTelegramID: int = None):
        super().__init__(electionID=electionID,
                         round=round,
                         roomIndex=roomIndex,
                         roomNameShort=roomNameShort,
                         roomNameLong=roomNameLong,
                         roomID=roomID,
                         roomTelegramID=roomTelegramID)

        self.members = list[ExtendedParticipant]

    def addMember(self, member: ExtendedParticipant):
        assert isinstance(member, ExtendedParticipant), "member must be an ExtendedParticipant"
        self.members.append(member)

    def getMembers(self) -> list[ExtendedParticipant]:
        return self.members

    def getMembersTelegramIDsIfKnown(self) -> list[str]:
        return [x for x in self.members if x.telegramID is not None and len(x.telegramID) > 2]
