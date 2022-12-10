import gettext
from datetime import datetime
from typing import TypedDict, Tuple, Dict

from app.constants.language import Language
from app.database import ExtendedRoom, ExtendedParticipant
_ = gettext.gettext
__ = gettext.ngettext


#
# In the future this will be a class that will be used to manage the text, depending on the language.
# For now, it is just an english text.
#


######## Multilanguage support in the future -= not translated yet =-
# cn = gettext.translation('base', localedir='locales', languages=['cn'])
# cn.install()
# _ = cn.gettext # Chinese


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

    def welcomeMessage(self, inviteLink: str, round: int, group: int, isLastRound: bool = False) -> str:
        assert isinstance(inviteLink, str), "groupLink must be a str"
        assert isinstance(round, int), "round must be an int"
        assert isinstance(group, int), "group must be an int"
        assert isinstance(isLastRound, bool), "isLastRound must be a bool"

        if isLastRound:
            return _("Wellcome to Eden Chief Delegate group." + self.newLine() + self.newLine() +
                     "Congratulations to everyone for making it this far! " + self.newLine())
        else:
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


    def timeIsAlmostUpGroup(self, timeLeftInMinutes: int, round: int, extendedRoom: ExtendedRoom) -> str:
        assert isinstance(timeLeftInMinutes, int), "timeLeftInMinutes must be an int"
        assert isinstance(round, int), "round must be an int"
        assert isinstance(extendedRoom, ExtendedRoom), "extendedRoom must be a ExtendedRoom"

        text: str = _("Only **%d minutes left** for voting in round %d. If you have not voted yet, "
                 "check the button bellow. Check the bot messages if you need to vote on bloks." + self.newLine() + self.newLine() +
                 "Vote statistic: "+ self.newLine()) % \
                 (timeLeftInMinutes, round + 1)

        participants: list[ExtendedParticipant] = extendedRoom.getMembers()

        for participant in participants:
            if participant.voteFor is None or participant.voteFor == "":
                text += _("• **%s** has not voted yet" + self.newLine()) % \
                        (participant.accountName)
            else:
                text += _("• **%s** votes for __%s__" + self.newLine()) % \
                        (participant.accountName, participant.voteFor)
        return text


    def timeIsAlmostUpButtons(self) -> tuple[str]:
        return [_("Vote on Eden members portal"),
                _("or on bloks.io")]


    def timeIsAlmostUpPrivate(self, timeLeftInMinutes: int, round: int, voteFor: str = None) -> str:
        assert isinstance(timeLeftInMinutes, int), "timeLeftInMinutes must be an int"
        assert isinstance(round, int), "round must be an int"

        if voteFor is None:
            return _("Only **%d minutes left** for voting in round %d. You have **not voted** yet. "
                     "Please vote on Eden members portal." + self.newLine() +
                     "In the case of portal connection"
                     " issues, you can choose ```bloks.io.```") % \
                (timeLeftInMinutes, round + 1)
        else:
            return _("Only **%d minutes left** for voting in round %d. You already voted for **%s**. "
                     "You can still change your decision on portal or on ```bloks.io.```") % \
                (timeLeftInMinutes, round + 1, voteFor)

    def sendPhotoHowToStartVideoCallCaption(self):
        return _("Start or join the video chat." + self.newLine() + self.newLine() +
                 "Once inside, click start recording in the menu.")

