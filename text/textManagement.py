import gettext
from datetime import datetime
from typing import TypedDict, Tuple, Dict

from constants import start_video_record_preview_paths, video_is_still_running_preview_path, \
    eden_portal_upload_video_url, eden_portal_url_action
from constants.language import Language
from database import ExtendedRoom, ExtendedParticipant

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

    def startCommandKnownTelegramID(self, userID: str) -> str:
        assert isinstance(userID, (str, type(None))), "telegramID must be a string or none"
        userID = str(userID) if userID is not None else "<Unknown ID>"
        return _("Welcome __%s__ " + self.newLine() + self.newLine() +
                 "Up Vote Bot will remind you about the next Eden election date, and guide  you through it. " + self.newLine() +
                 "There is no spam, so keep the notifications on!") % (userID)

    def startCommandNotKnownTelegramID(self, telegramID: str) -> str:
        assert isinstance(telegramID, (str, type(None))), "telegramID must be a string"
        telegramID = str(telegramID) if telegramID is not None else "<Unknown ID>"
        return _("Hi __%s__, " + self.newLine() + self.newLine() +
                 "you are now registered with the Up Vote Bot, and can receive notifications, "
                 "but you are not yet inducted into Eden.") % (telegramID)

    def donateCommandtext(self) -> str:
        return _("Support the development of Up Vote Bot features")

    def donateCommandtextButon(self) -> str:
        return _("Pomelo (Up Vote Bot)")

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


class VideoReminderTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def videoReminder(self, group: int, round: int, expiresText: str) -> str:
        assert isinstance(round, int), "round must be an int"
        assert isinstance(group, int), "group must be an int"
        assert isinstance(expiresText, str), "expiresText must be a str"
        return _("Hey election participants!" + self.newLine() +
                 "I am here to remind you that your group %s from round %s still "
                 "didn't upload the election video. Uploads video time expires %s") % \
            (group, round, expiresText)

    def invitationLinkToTheGroupButons(self, inviteLink: str, bloksLink: str) -> tuple[Button, Button, Button]:
        # it returns tuple of all the buttons(text link)
        assert isinstance(inviteLink, str), "groupLink must be a str"
        assert isinstance(bloksLink, str), "bloksLink must be a str"
        return Button(text="Join/Enter the group", value=inviteLink), \
            Button(text="Update video", value=bloksLink), \
            Button(text="Update on bloks.io", value=bloksLink),

    def videoReminderButtonText(self, groupLink: str) -> tuple[Button]:
        assert isinstance(groupLink, str), "groupLink must be a str"
        return Button(text="Upload on the portal", value=eden_portal_upload_video_url), \
               Button(text="Coordinate with your group", value=groupLink),


class CommandResponseTextManagement(TextManagement):
    #not yet in use
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def recording(self) -> str:
        return _("Recording has been started")

    def recordingImagePath(self) -> str:
        return start_video_record_preview_paths

class EndOfRoundTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def roundIsOverAndVideoIsRunning(self):
        return _("It appears you didn't end the video chat. Rejoin the chat and follow the two steps. "
                 "It stops recording and saves it to your `Saved Messages`.")

    def roundIsOverAndVideoIsNotRunning(self):
        return _("Thank you for participating! User that started and ended the recording check your `Saved Messages` "
                 "for video, and upload it after elections are done.")

    def endVideoChatImagePath(self) -> str:
        return video_is_still_running_preview_path

    def roundIsOverUploadVideoLink(self):
        return eden_portal_upload_video_url

    def roundIsOverButton(self, inviteLink: str):
        assert isinstance(inviteLink, str), "inviteLink must be a str"
        return Button(text="Upload on the portal", value=inviteLink),

class CommunityGroupManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def invitationToGroup(self) -> str:
        return _("You have a valid Eden SBT, that makes you eligible to participate in members only group." + self.newLine()
                + "See you there!")
    def invitationToGroupButton(self, inviteLink: str) -> Button:
        assert isinstance(inviteLink, str), "inviteLink must be a str"
        return Button(text="Join the community group", value=inviteLink),

class VideCallTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def videoHasBeenStarted(self) -> str:
        return _("One of the participants needs to follow 4 steps until everyone sees the red dot.")

    def videoHasBeenStopped(self) -> str:
        return _("Thank you for participating! User that started and ended the recording "
                 "check your `Saved Messages` for video, and upload it after elections are done.")

    def videoHasBeenStoppedButtonText(self, inviteLink: str) -> Button:
        # it returns tuple of all the buttons(text link)
        assert isinstance(inviteLink, str), "groupLink must be a str"
        return Button(text="Upload on the portal", value=inviteLink),  # must be with comma - to store it as a tuple

    def startRecordingGetImagePaths(self) -> list[str]:
        # get the image from the file - in the future it will be more dynamic - more languages
        if isinstance(start_video_record_preview_paths, list) is False:
            raise TypeError("start_video_record_preview_paths must be a list")
        return start_video_record_preview_paths


    def videoIsStillRunningText(self) -> str:
        return _("It appears you didn't end the video chat. Rejoin the chat and follow the two steps. "
                 "It stops recording and saves it to your `Saved Messages`.")


class GroupCommunicationTextManagement(TextManagement):
    def __init__(self, language: Language = Language.ENGLISH):
        super().__init__(language)

    def invitationLinkToTheGroup(self, round: int, isLastRound: bool = False) -> str:
        assert isinstance(round, int), "round must be an int"
        assert isinstance(isLastRound, bool), "isLastRound must be a bool"
        if isLastRound:
            return _("Hey," + self.newLine() +
                     "Congratulation for making it this far." + self.newLine() +
                     "Please join the Eden Chief Delegate group using this link bellow:")
        else:
            return _("Hey," + self.newLine() +
                     "Round %d has started." + self.newLine() +
                     "Please join the group using this link bellow:") % (round + 1)

    def invitationLinkToTheGroupButons(self, inviteLink: str) -> tuple[Button]:
        # it returns tuple of all the buttons(text link)
        assert isinstance(inviteLink, str), "groupLink must be a str"
        return Button(text="Join the group", value=inviteLink),  # must be with comma - to store it as a tuple

    def welcomeMessage(self, inviteLink: str, round: int, group: int, isLastRound: bool = False) -> str:
        assert isinstance(inviteLink, str), "inviteLink must be a str"
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
                      "Vote statistic: " + self.newLine()) % \
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
