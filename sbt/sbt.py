from datetime import datetime

class SBT:
    def __init__(self, round: int, received: datetime):
        assert isinstance(round, int), "round must be int"
        assert isinstance(received, datetime), "received must be datetime"
        self.round = round
        self.received = received

    def __eq__(self, other):
        if not isinstance(other, SBT):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.round == other.round and self.received == other.received

    def __str__(self):
        return "SBT; round:" + str(self.round) + ", received: " + str(self.received)