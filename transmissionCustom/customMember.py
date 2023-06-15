from enum import Enum

from log.log import Log
from transmissionCustom import REMOVE_AT_SIGN_IF_EXISTS

LOGar = Log(className="AdminRights")
LOG = Log(className="CustomMember")

"""
    "_": "ChatPrivileges",
    "can_manage_chat": true,
    "can_delete_messages": true,
    "can_manage_video_chats": true,
    "can_restrict_members": true,
    "can_promote_members": false,
    "can_change_info": true,
    "can_post_messages": false,
    "can_edit_messages": false,
    "can_invite_users": true,
    "can_pin_messages": true,
    "is_anonymous": false
"""


class AdminRights:
    def __init__(self, isAdmin: bool = False,
                 canManageChat: bool = False, canDeleteMessages: bool = False,
                 canManageVideoChats: bool = False, canRestrictMembers: bool = False,
                 canPromoteMembers: bool = False, canChangeInfo: bool = False,
                 canPostMessages: bool = False, canEditMessages: bool = False,
                 canInviteUsers: bool = False, canPinMessages: bool = False,
                 isAnonymous: bool = False):
        assert isinstance(isAdmin, bool), "isAdmin should be bool"

        assert isinstance(canManageChat, bool), "canManageChat should be bool"
        assert isinstance(canDeleteMessages, bool), "canDeleteMessages should be bool"
        assert isinstance(canManageVideoChats, bool), "canManageVideoChats should be bool"
        assert isinstance(canRestrictMembers, bool), "canRestrictMembers should be bool"
        assert isinstance(canPromoteMembers, bool), "canPromoteMembers should be bool"
        assert isinstance(canChangeInfo, bool), "canChangeInfo should be bool"
        assert isinstance(canPostMessages, bool), "canPostMessages should be bool"
        assert isinstance(canEditMessages, bool), "canEditMessages should be bool"
        assert isinstance(canInviteUsers, bool), "canInviteUsers should be bool"
        assert isinstance(canPinMessages, bool), "canPinMessages should be bool"
        assert isinstance(isAnonymous, bool), "isAnonymous should be bool"

        # if isAdmin is False, all other parameters should be False
        self.isAdmin = isAdmin
        if self.isAdmin is False:
            LOGar.debug("AdminRights: Not admin rights")
            self.nonAdminParameters()
            return

        LOG.debug("AdminRights: Admin rights")
        self.canManageChat = canManageChat
        self.canDeleteMessages = canDeleteMessages
        self.canManageVideoChats = canManageVideoChats
        self.canRestrictMembers = canRestrictMembers
        self.canPromoteMembers = canPromoteMembers
        self.canChangeInfo = canChangeInfo
        self.canPostMessages = canPostMessages
        self.canEditMessages = canEditMessages
        self.canInviteUsers = canInviteUsers
        self.canPinMessages = canPinMessages
        self.isAnonymous = isAnonymous

    def __str__(self):
        return "AdminRights(isAdmin=" + "True" if self.isAdmin else "False" + \
               ", canManageChat=" + "True" if self.canManageChat else "False" + \
               ", canDeleteMessages=" + "True" if self.canDeleteMessages else "False" + \
               ", canManageVideoChats=" + "True" if self.canManageVideoChats else "False" + \
               ", canRestrictMembers=" + "True" if self.canRestrictMembers else "False" + \
               ", canPromoteMembers=" + "True" if self.canPromoteMembers else "False" + \
               ", canChangeInfo=" + "True" if self.canChangeInfo else "False" + \
               ", canPostMessages=" + "True" if self.canPostMessages else "False" + \
               ", canEditMessages=" + "True" if self.canEditMessages else "False" + \
               ", canInviteUsers=" + "True" if self.canInviteUsers else "False" + \
               ", canPinMessages=" + "True" if self.canPinMessages else "False" + \
               ", isAnonymous=" + "True" if self.isAnonymous else "False" + \
               ")"

    def nonAdminParameters(self):
        self.canManageChat = False
        self.canDeleteMessages = False
        self.canManageVideoChats = False
        self.canRestrictMembers = False
        self.canPromoteMembers = False
        self.canChangeInfo = False
        self.canPostMessages = False
        self.canEditMessages = False
        self.canInviteUsers = False
        self.canPinMessages = False
        self.isAnonymous = False


class Promotion:
    def __init__(self, userId: str, username: str = None):
        assert isinstance(userId, str), "userId should be str"
        assert isinstance(username, (str, type(None))), "username should be str or None"

        self.userId = userId
        self.username = username
        if self.username is not None:
            self.username = REMOVE_AT_SIGN_IF_EXISTS(self.username.lower())


    def isSame(self, userID: str = None, username: str = None):
        assert isinstance(userID, (str, type(None))), "userID should be str or None"
        assert isinstance(username, (str, type(None))), "username should be str or None"

        if username is not None:
            username = REMOVE_AT_SIGN_IF_EXISTS(username.lower())

        if userID is None and username is None:
            LOG.exception("CustomMember.isSame; One of the parameters (userID, username) should be not None")
            return False

        if userID is not None and self.userId == userID:
            return True

        if username is not None and self.username == username:
            return True

        return False

    def __eq__(self, other):
        if isinstance(other, CustomMember):
            return self.userId == other.userId or self.username == other.username
        return False

    def __str__(self):
        return "Promotion(userId=" + self.userId + ", username=" + str(self.username) + ")"

class MemberStatus(Enum):
    OTHER = 0,
    OWNER = 1,
    ADMINISTRATOR = 2,
    MEMBER = 3

class CustomMember:
    def __init__(self, userId: str, memberStatus: MemberStatus,  isBot: bool = False, username: str = None, tag: str = None, \
                 adminRights: AdminRights = None, promotedBy: Promotion = None, isUnknown: bool = False):
        assert isinstance(userId, str), "userId should be str"
        assert isinstance(memberStatus, MemberStatus), "memberStatus should be MemberStatus"
        assert isinstance(isBot, bool), "isBot should be bool"
        assert isinstance(username, (str, type(None))), "username should be str or None"
        assert isinstance(tag, (str, type(None))), "tag should be str or None"
        assert isinstance(adminRights, (AdminRights, type(None))), "isAdmin should be type of AdminRights or None"
        assert isinstance(promotedBy, (Promotion, type(None))), "promotion should be type of Promotion or None"
        assert isinstance(isUnknown, bool), "isUnknown should be bool"
        # if adminRights is not None, promotedBy should be not None!

        self.userId = userId
        self.memberStatus = memberStatus
        self.username = username
        if self.username is not None:
            self.username = REMOVE_AT_SIGN_IF_EXISTS(self.username.lower())

        self.isBot = isBot
        self.tag = tag

        # admin rights should always be AdminRights object - not None
        if adminRights is None or adminRights.isAdmin is False:
            self.adminRights = AdminRights(isAdmin=False)
        else:
            self.adminRights = adminRights
            #if promotedBy is None:
            #    raise ValueError("promotedBy should be not None if adminRights is set")
        self.promotedBy = promotedBy

        # who promoted this user to admin or is it owner

        self.isUnknown = isUnknown

    def __str__(self):
        return "CustomMember(userId=" + str(self.userId) + \
               ", isBot=" + "True" if self.isBot else "False" + \
               ", username=" + str(self.username) if self.username is not None else "None" + \
               ", memberStatus=" + str(self.memberStatus) + \
               ", tag=" + str(self.tag) if self.tag is not None else "None" + \
               ", adminRights=" + str(self.adminRights) + \
               ", isUnknown=" + "True" if self.isUnknown else "False" + \
               ", promotedBy=" + str(self.promotedBy) + \
               ")"

    __repr__ = __str__

    def __eq__(self, other):
        if isinstance(other, CustomMember):
            return self.userId == other.userId or self.username == other.username
        return False

    def setIsUnknown(self, isUnknown: bool):
        assert isinstance(isUnknown, bool), "isUnknown should be bool"
        self.isUnknown = isUnknown

    def isSame(self, userID: str = None, username: str = None):
        assert isinstance(userID, (str, type(None))), "userID should be str or None"
        assert isinstance(username, (str, type(None))), "username should be str or None"

        if username is not None:
            username = REMOVE_AT_SIGN_IF_EXISTS(username.lower())

        if userID is None and username is None:
            LOG.exception("CustomMember.isSame; One of the parameters (userID, username) should be not None")
            return False

        if userID is not None and self.userId == userID:
            return True

        if username is not None and self.username == username:
            return True

        return False
