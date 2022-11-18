import gettext
from typing import TypedDict, Tuple, Dict

from app.constants.language import Language

_ = gettext.gettext
__ = gettext.ngettext


#
# In the future this will be a class that will be used to manage the text, depending on the language.
# For now, it is just an english text.
#


class Button(TypedDict):
    text: str
    value: str


class TextManagement:

    def __init__(self, language: Language = Language.ENGLISH):
        assert isinstance(language, Language), "language must be a type of Language(Enum)"
        self.language: Language = language

    def setLanguage(self, language: Language):
        assert isinstance(language, Language), "language must be a type of Language(Enum)"
        self.language = language

    def getLanguage(self) -> Language:
        return self.language

    def newLine(self) -> str:
        return "\n"


class GroupCommunicationTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def invitationLinkToTheGroup(self, round: int) -> str:
        assert isinstance(round, int), "round must be an int"
        return _("Hey," + self.newLine() +
                 "Round %d has started." + self.newLine() +
                 "Please join the group using this link bellow:") % (round)

    def invitationLinkToTheGroupButons(self, inviteLink: str) -> tuple[Button]:
        # return a dict with the dictionary of the buttons(text link)
        assert isinstance(inviteLink, str), "groupLink must be a str"
        return Button(text="Join the group", value=inviteLink),

    def wellcomeMessage(self, inviteLink: str, round: int) -> str:
        assert isinstance(round, int), "round must be an int"
        return _("Welcome to to Eden communication group!" + self.newLine() +
                 "This is round %d. " + self.newLine() + self.newLine() +
                 "If any participant is not joined yet (and should be), send this invite link:" + self.newLine() +
                 "%s") % (round, inviteLink)

    def participantsInTheRoom(self) -> str:
        return _("Participants in the room: \n")

    def participant(self, accountName: str, participantName: str, telegramID: str) -> str:
        assert isinstance(accountName, str), "electionName must be a str"
        assert isinstance(participantName, str), "participantName must be a string"
        assert isinstance(telegramID, str), "telegramId must be a string"

        return _("•Eden name: **%s** (name: %s); TelegramID: __%s__") % (
                    accountName,  # fist parameter
                    participantName if participantName is not None else "/",  # second parameter
                    telegramID if telegramID is not None and len(telegramID) > 2 else "<NOT_KNOWN_TELEGRAM_ID>")

    def demoMessageInCreateGroup(self) -> str:
        return _("ALERT: Participants above are not really in the group. This is just a demo. Only admins added")
