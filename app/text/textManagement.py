import gettext
from datetime import datetime
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


class WellcomeMessageTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def getWellcomeMessage(self, participantAccountName: str) -> str:
        assert isinstance(participantAccountName, str), "participantAccountName must be a string"
        return _("Welcome __%s__ to the room!") % participantAccountName


class ElectionTimeIsUpTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def groupMessage(self, roundEnd: datetime, messageTime: datetime, participant: list(Participant)) -> str:
        assert isinstance(roundEnd, datetime), "roundEnd must be a datetime"
        assert isinstance(messageTime, datetime), "messageTime must be a datetime"
        assert isinstance(participant, list), "participant must be a list"

        return _("Election __%s__ with description __%s__ has been created with ID __%d__") % (
            electionName, electionDescription, electionID)

class BotCommunicationManagement(TextManagement):

    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def startCommandKnownTelegramID(self, telegramID: str) -> str:
        assert isinstance(telegramID, (str, type(None))), "telegramID must be a string"
        telegramID = str(telegramID) if telegramID is not None else "<Unknown ID>"
        return _("Welcome __%s__ !" + self.newLine() + self.newLine() +
                 "Now you will be reminded about next Eden election date, and guides  you through it. " + self.newLine() +
                 "There is no spam, so keep the notifications on!") % (telegramID)

    def startCommandNotKnownTelegramID(self, telegramID: str) -> str:
        assert isinstance(telegramID, (str, type(None))), "telegramID must be a string"
        telegramID = str(telegramID) if telegramID is not None else "<Unknown ID>"
        return _("Hi __%s__, " + self.newLine() + self.newLine() +
                 "you are not yet inducted into Eden.") % (telegramID)

    def startCommandNotKnownTelegramIDButtonText(self):
        return _("Ask for an invite")

    def newUserCommand(self, telegramID: str) -> str:
        assert isinstance(telegramID, (str, type(None))), "telegramID must be a string"
        telegramID = str(telegramID) if telegramID is not None else "<Unknown ID>"
        return _("Wellcome %s to the chat!") % (telegramID)

    def infoCommand(self) -> str:
        return _("This bot reminds you about the next Eden election date and guides you through it. " + self.newLine() +
                 "There is no spam, so keep the notifications on!")

    def infoCommandButtonText(self) -> str:
        return _("Learn more about Eden")



class GroupCommunicationTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def invitationLinkToTheGroup(self, round: int) -> str:
        assert isinstance(round, int), "round must be an int"
        return _("Hey," + self.newLine() +
                 "Round %d has started." + self.newLine() +
                 "Please join the group using this link bellow:") % (round + 1)

    def invitationLinkToTheGroupButons(self, inviteLink: str) -> tuple[Button]:
        # return a dict with the dictionary of the buttons(text link)
        assert isinstance(inviteLink, str), "groupLink must be a str"
        return Button(text="Join the group", value=inviteLink),

    def welcomeMessage(self, inviteLink: str, round: int, group: int) -> str:
        assert isinstance(inviteLink, str), "groupLink must be a str"
        assert isinstance(round, int), "round must be an int"
        assert isinstance(group, int), "group must be an int"
        return _("Welcome to Eden Group %d in the Round %d." + self.newLine() + self.newLine() +
                 "If any participant is not joined yet (and should be), send them this invite link:" + self.newLine() +
                 "%s") % (group, round + 1, inviteLink)

    def participantsInTheRoom(self) -> str:
        return _("Participants in the room: \n")

    def participant(self, accountName: str, participantName: str, telegramID: str) -> str:
        assert isinstance(accountName, str), "electionName must be a str"
        assert isinstance(participantName, str), "participantName must be a string"
        assert isinstance(telegramID, str), "telegramId must be a string"

        return _("• Eden: **%s**\n"
                 "\t name: %s\n"
                 "\t Telegram: __%s__") % (
                    accountName,  # fist parameter
                    participantName if participantName is not None else "/",  # second parameter
                    telegramID if telegramID is not None and len(telegramID) > 2 else "<NOT_KNOWN_TELEGRAM_ID>")

    def demoMessageInCreateGroup(self) -> str:
        return _("__ALERT: Participants above are not really in the group. This is just a demo. Only testers added__")


    def timeIsAlmostUpGroup(self, timeLeftInMinutes: int, round: int) -> str:
        assert isinstance(timeLeftInMinutes, int), "timeLeftInMinutes must be an int"
        assert isinstance(round, int), "round must be an int"

        return _("Only **%d minutes left** for voting in round %d. If you have not voted yet, "
                 "check the button bellow. Check the bot messages if you need to vote on bloks.") % \
                (round, timeLeftInMinutes)

    def timeIsAlmostUpButtons(self) -> tuple[str]:
        return [_("Vote on Eden members portal", "or on blocks.io")]


    def timeIsAlmostUpPrivate(self, timeLeftInMinutes: int, round: int) -> str:
        assert isinstance(timeLeftInMinutes, int), "timeLeftInMinutes must be an int"
        assert isinstance(round, int), "round must be an int"

        return _("Only **%d minutes left** for voting in round %d. In the case of portal connection"
                 " issues, you can choose blocks.") % \
                (round, timeLeftInMinutes)

    def sendPhotoHowToStartVideoCallCaption(self):
        return _("Start or join the video chat." + self.newLine() + self.newLine() +
                 "Once inside, click start recording in the menu.")

