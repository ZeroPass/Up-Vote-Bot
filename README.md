#  Up Vote Bot

Read its description and donate at [pomelo.io/grants/bot4eden](https://pomelo.io/grants/bot4eden)!

The bot chills in Telegram at [@Up_Vote_Bot](https://t.me/Up_Vote_Bot). Between elections it might not respond due to maintanence. Use the command /status, to check if its online at the time.

It is a bot written in Python language which main purpose is to support [Eden](https://genesis.eden.eoscommunity.org/) elections, but might expand in the future.

## Preconditions

- Python 3.9.12

## Installation

Under library custom there needs to be installed 2 libraries:

- [abieos-python](https://pypi.org/project/abieos-python/)
- [dfuse-python](https://pypi.org/project/dfuse/)

Also install these libraries:
- loguru~=0.6.0
- Pyrogram~=2.0.41
- psycopg2~=2.9.3
- PyMySQL~=1.0.2
- setuptools~=62.1.0

** it will be combined in requirement.txt in the future

## Usage

```python
# start python script
python edenBot.py
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
Distributed under the LGPL 3.0 license. 

See [link](https://www.gnu.org/licenses/lgpl-3.0.html/) for more information.
