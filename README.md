# Up Vote Bot
We are running the [Up Vote Bot in Telegram](https://t.me/Up_Vote_Bot).  
Read about the progress and donate at [pomelo.io/grants/bot4eden](https://pomelo.io/grants/bot4eden).

## Dockerization
- Dockerization for bot is available [here](https://github.com/ZeroPass/Up-Vote-Bot-Dockerized).


## Additional info:
- Bot has badge/text - 'has access to messages' - we cannot remove it because of admin rights (also changing privacy mode (in Botfather chat) to ONE cannot remove this badge). If bot has admin rights, it gets the badge automatic (https://core.telegram.org/bots/faq#what-messages-will-my-bot-get).

- Sending limit is around 30 messages per second (https://core.telegram.org/bots/faq#how-can-i-message-all-of-my-bot-39s-subscribers-at-once)
- We detected the limit of 'group creation action' (around 50 groups per dey per bot)
- Renaming group has limit around 8 groups in one actions set (rename every ~30 seconds)

## Delay
- There are 2 types of upcoming event messages
  - X min till the end of round,
  - X hours/days till the start of elections.
- When the message was sent to the user, app writes the record (with commit) on database -single row. For faster exection it should write in bulk and create one commit.
  
