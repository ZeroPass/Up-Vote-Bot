from app.database.room import Room
from app.database.extendedParticipant import ExtendedParticipant


class ExtendedRoom(Room):
    def __init__(self, electionID: int, round: int, roomIndex: int, roomNameShort: str, roomNameLong: str,
                 members: list[ExtendedParticipant] = None, roomID: int = None, roomTelegramID: str = None, ):
            assert isinstance(electionID, int), "electionID must be int"
            assert isinstance(roomNameShort, str), "roomNameShort must be str"
            assert isinstance(roomNameLong, str), "roomNameLong must be str"
            assert isinstance(round, int), "round must be int"
            assert isinstance(roomIndex, int), "roomIndex must be int"
            assert isinstance(roomTelegramID, (str, type(None))), "roomTelegramID must be int or None"
            assert isinstance(roomID, (int, type(None))), "roomID must be int or None"
            assert isinstance(members, (list, type(None))), "members must be list"

            super().__init__(electionID=electionID,
                             round=round,
                             roomIndex=roomIndex,
                             roomNameShort=roomNameShort,
                             roomNameLong=roomNameLong,
                             roomID=roomID,
                             roomTelegramID=roomTelegramID)
            if members is None:
                self.members = []
            else:
                self.members = members

    @classmethod
    def fromRoom(cls, room: Room, members: list[ExtendedParticipant] = None):
        assert isinstance(room, Room), "Room must be of type Room"
        assert isinstance(members, (list, type(None))), "members must be list or None"

        return cls(electionID=room.electionID,
                   round=room.round,
                   roomIndex=room.roomIndex,
                   roomNameShort=room.roomNameShort,
                   roomNameLong=room.roomNameLong,
                   roomID=room.roomID,
                   roomTelegramID=room.roomTelegramID)

    def addMember(self, member: ExtendedParticipant):
        assert isinstance(member, ExtendedParticipant), "member must be an ExtendedParticipant"
        self.members.append(member)

    def getMembers(self) -> list[ExtendedParticipant]:
        return self.members

    def getMembersTelegramIDsIfKnown(self) -> list[str]:
        return [x.telegramID for x in self.members if x.telegramID is not None and len(x.telegramID) > 2]
