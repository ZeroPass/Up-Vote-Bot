import enum
from datetime import datetime, timedelta

from constants import telegram_bot_name
from database.comunityParticipant import CommunityParticipant
from database.participant import Participant
from log import Log
from transmissionCustom import REMOVE_AT_SIGN_IF_EXISTS

LOG = Log(className="CommunityList")
class CommunityListException(Exception):
    pass


class CommunityListState(enum.Enum):
    CURRENT: int = 0
    GOAL: int = 1

class CommunityList:
    def __init__(self, inducted: list[Participant]):
        LOG.info("Creating CommunityList object")
        self.state: dict = \
            {
                CommunityListState.CURRENT: None,
                CommunityListState.GOAL: None
            }

        for i in inducted:
            assert isinstance(i, Participant), "inducted must be Participant"
        self.inducted: list[Participant] = inducted


    def isStateSet(self, state: CommunityListState):
        assert isinstance(state, CommunityListState), "state must be CommunityListState"
        return self.state.get(state) is not None

    def getState(self, state: CommunityListState):
        assert isinstance(state, CommunityListState), "state must be CommunityListState"
        if self.isStateSet(state) is False:
            raise CommunityListException("State " + str(state) + " is not set")
        return self.state.get(state)

    def append(self, state: CommunityListState, item: CommunityParticipant):
        assert isinstance(state, CommunityListState), "state must be CommunityListState"
        assert isinstance(item, CommunityParticipant), "item must be CommunityParticipant"
        if self.isStateSet(state) is False:
            self.state[state] = list[CommunityParticipant]()
        self.state.get(state).append(item)

    def usersThatAreNotInGroupButShouldBe(self) -> list[CommunityParticipant]:
        try:
            LOG.debug("Getting users that are not in group but should be")
            if len(self.inducted) == 0:
                raise CommunityListException("CommunityList.usersThatAreNotInGroupButShouldBe; Inducted accounts are not set")

            if self.isStateSet(state=CommunityListState.CURRENT) is False or \
                    self.isStateSet(state=CommunityListState.GOAL) is False:
                raise CommunityListException("Current state is not set")
            found: list[CommunityParticipant] = list[CommunityParticipant]()
            for goalU in self.state[CommunityListState.GOAL]:
                foundParticipant: list[CommunityParticipant] = [x for x in self.state.get(CommunityListState.CURRENT)
                                                          if x.accountName == goalU.accountName]

                if len(foundParticipant) == 0:
                    LOG.debug("User " + goalU.accountName + " is not in group but should be(tg: " +
                              str(goalU.telegramID) + ")")
                    found.append(goalU)

            # add inducted accounts
            for inductedU in self.inducted:
                foundParticipant: list[CommunityParticipant] = [x for x in found
                                                                if x.accountName == inductedU.accountName]

                foundParticipantCurrent: list[CommunityParticipant] = [x for x in self.state.get(CommunityListState.CURRENT)
                                                                if x.accountName == inductedU.accountName]

                if len(foundParticipant) == 0 and len(foundParticipantCurrent) == 0:
                    LOG.debug("User " + inductedU.accountName + " is not in group but should be")
                    #accountName: str, roomID: int, participationStatus: bool, telegramID: str, nftTemplateID: int,
                    found.append(CommunityParticipant(accountName=inductedU.accountName,
                                                      roomID=inductedU.roomID,
                                                      participationStatus=inductedU.participationStatus,
                                                      telegramID=inductedU.telegramID,
                                                      nftTemplateID=inductedU.nftTemplateID,
                                                      participantName=inductedU.participantName))


            return found
        except Exception as e:
            LOG.exception("CommunityList.usersThatAreNotInGroupButShouldBe; exception: " + str(e))

    def usersThatAreInGroupButShouldNotBe(self) -> list[CommunityParticipant]:
        try:
            LOG.debug("Getting users that are in group but should not be")
            if len(self.inducted) == 0:
                raise CommunityListException("CommunityList.usersThatAreInGroupButShouldNotBe; Inducted accounts are not set")

            if self.isStateSet(state=CommunityListState.CURRENT) is False or \
                    self.isStateSet(state=CommunityListState.GOAL) is False:
                raise CommunityListException("Current state is not set")

            found: list[CommunityParticipant] = list[CommunityParticipant]()
            for currentU in self.state[CommunityListState.CURRENT]:
                foundParticipant: list[CommunityParticipant] = [x for x in self.state.get(CommunityListState.GOAL)
                                                          if x.accountName == currentU.accountName]
                inductedParticipant: list[Participant] = [x for x in self.inducted
                                                            if x.accountName == currentU.accountName]

                if len(inductedParticipant) > 0:
                    LOG.debug("User " + inductedParticipant[0].accountName + " is inducted, do not remove it")

                if len(foundParticipant) == 0 and len(inductedParticipant) == 0:
                    # not in group but also not in inducted in last X months
                    if currentU.customMember is not None and currentU.customMember.adminRights is not None \
                            and currentU.customMember.adminRights.isAdmin is True:
                            #currentU.customMember.tag is not None and \
                            #currentU.customMember.tag != "":
                        LOG.debug("User " + currentU.accountName + " is admin with tag, do not remove it")
                        continue

                    LOG.debug("User " + currentU.accountName + " is in group but should not be "
                                                               "(tg: " +str(currentU.telegramID) +")")
                    found.append(currentU)
            return found
        except Exception as e:
            LOG.exception("CommunityList.usersThatAreInGroupButShouldNotBe exception: " + str(e))

    def usersThatAreNotYetAdminsButShouldBe(self) -> list[CommunityParticipant]:
        try:
            LOG.debug("Getting users that are not yet admins but should be")
            if self.isStateSet(state=CommunityListState.CURRENT) is False or \
                    self.isStateSet(state=CommunityListState.GOAL) is False:
                raise CommunityListException("Current state is not set")
            found: list[CommunityParticipant] = list[CommunityParticipant]()
            for goalU in self.state[CommunityListState.GOAL]:
                if goalU.customMember is None or \
                        (goalU.customMember is not None and goalU.customMember.adminRights.isAdmin is False):
                    continue
                foundParticipantAdmin: CommunityParticipant = [x for x in self.state.get(CommunityListState.CURRENT)
                                                          if x.accountName == goalU.accountName and
                                                             x.customMember is not None and
                                                             x.customMember.adminRights.isAdmin is True]
                if len(foundParticipantAdmin) == 0:
                    LOG.debug("User " + goalU.accountName + " is not admin but should be")
                    found.append(goalU)
            return found
        except Exception as e:
            LOG.exception("CommunityList.usersThatAreNotYetAdminsButShouldBe exception: " + str(e))

    def usersThatAreAdminsButShouldNotBe(self) -> list[CommunityParticipant]:
        try:
            LOG.debug("Getting users that are admins but should not be")
            if self.isStateSet(state=CommunityListState.CURRENT) is False or \
                    self.isStateSet(state=CommunityListState.GOAL) is False:
                raise CommunityListException("Current state is not set")
            found: list[CommunityParticipant] = list[CommunityParticipant]()
            for currentU in self.state[CommunityListState.CURRENT]:
                if (currentU.customMember is not None and currentU.customMember.adminRights.isAdmin is False)\
                        or currentU.customMember is None:
                    # current user is not admin, so we can skip him
                    continue
                if currentU.customMember is not None and currentU.customMember.adminRights.isAdmin is True:
                   #(currentU.customMember.tag is not None and currentU.customMember.tag != "" ):

                    if currentU.customMember.promotedBy is not None:
                        kvb = str(currentU.customMember.promotedBy.username).lower()
                        kva = str(REMOVE_AT_SIGN_IF_EXISTS(telegram_bot_name)).lower()
                        LOG.debug(kva + " " + kvb + " " + str(kva == kvb))
                    #another check because of redability - if promoted by other admin, we can skip him
                    if currentU.customMember.promotedBy is not None and \
                        str(currentU.customMember.promotedBy.username).lower() != str(REMOVE_AT_SIGN_IF_EXISTS(telegram_bot_name)).lower():
                        LOG.debug("User " + currentU.accountName + " is admin but promoted by " +
                                    str(currentU.customMember.promotedBy.username) + \
                                  "(tg: " + str(currentU.telegramID) + ")")
                        continue

                    foundParticipant: CommunityParticipant = [x for x in self.state.get(CommunityListState.GOAL)
                                                              if x.accountName == currentU.accountName and
                                                              x.customMember is not None and
                                                              x.customMember.adminRights.isAdmin is True]

                    if len(foundParticipant) == 0:
                        LOG.debug("User " + currentU.accountName + " is admin but should not be")
                        found.append(currentU)
            return found
        except Exception as e:
            LOG.exception("CommunityList.usersThatAreAdminsButShouldNotBe exception: " + str(e))

    def usersWithWrongTags(self) -> list[CommunityParticipant]:
        try:
            LOG.debug("Getting users with wrong tag")
            if self.isStateSet(state=CommunityListState.CURRENT) is False or \
                    self.isStateSet(state=CommunityListState.GOAL) is False:
                raise CommunityListException("Current state is not set")
            found: list[CommunityParticipant] = list[CommunityParticipant]()
            for goalU in self.state[CommunityListState.GOAL]:

                LOG.success("User " + goalU.accountName + "; customMember: " + str(goalU.customMember))
                if (goalU.customMember is not None and goalU.customMember.adminRights.isAdmin is False and
                    goalU.customMember.tag is not None and goalU.customMember.tag != "") \
                        or goalU.customMember is None:
                    # goal the user is not admin, so we can skip him - only admins can have tags
                    continue

                foundParticipant: CommunityParticipant = [x for x in self.state.get(CommunityListState.CURRENT)
                                                          if x.accountName == goalU.accountName]
                if len(foundParticipant) > 1:
                    LOG.success("Found participant length: " + len(foundParticipant))
                if len(foundParticipant) != 0:
                    currentUser: CommunityParticipant = foundParticipant[0]
                    if currentUser.customMember.promotedBy is not None and \
                            str(currentUser.customMember.promotedBy.username).lower() != str(
                        REMOVE_AT_SIGN_IF_EXISTS(telegram_bot_name)).lower():
                        LOG.debug("User " + currentUser.accountName + "with tg: (" +
                                  str(currentUser.telegramID) +
                                  ") has promoted by " + str(currentUser.customMember.promotedBy.username) +
                                  " Tag: " + (currentUser.customMember.tag if currentUser.customMember.tag is not None else "None") +
                                  " Do not change it")
                        continue

                    if goalU.customMember.tag != currentUser.customMember.tag:
                        found.append(goalU)
                        LOG.debug("User " + foundParticipant[0].accountName + " has different tag")
                        LOG.info("Current tag: " + currentUser.customMember.tag if currentUser.customMember.tag is not None else "None" +
                                 ", goal Tag: " + (currentUser.customMember.tag if currentUser.customMember.tag is not None else "None"))
            return found
        except Exception as e:
            LOG.exception("CommunityList.usersWithWrongTag exception: " + str(e))



def main():
    kva = 9

if __name__ == "__main__":
    main()

