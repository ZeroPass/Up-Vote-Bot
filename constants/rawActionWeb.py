import urllib.parse as urlparse
from urllib.parse import urlencode

from constants import blocksIoLinkToTheContract
from log import Log


def setQueryParameter(url: str, param_name: str, param_value: str):
    """Given a URL, set or replace a query parameter and return the
    modified URL.
    """
    assert isinstance(url, str), "url must be string"
    assert isinstance(param_name, str), "param_name must be string"
    assert isinstance(param_value, str), "param_value must be string"

    scheme, netloc, path, query_string, fragment = urlparse.urlsplit(url)
    query_params = urlparse.parse_qs(query_string)

    query_params[param_name] = [param_value]
    new_query_string = urlencode(query_params, doseq=True)

    return urlparse.urlunsplit((scheme, netloc, path, new_query_string, fragment))


LOG = Log(className="RawActionWeb")


class RawActionWeb:
    """RawActionWeb class."""

    def __init__(self):
        """Initialize RawActionWeb class."""

        self.baseUrl = blocksIoLinkToTheContract

    def electOpt(self, member: str = None):
        """action: electOpt"""
        assert isinstance(member, (str, type(None))), "member must be a string or None"


        LOG.debug("electopt; member: " + member if member is not None else "None")

        url = setQueryParameter(self.baseUrl, "action", "electopt")
        url = setQueryParameter(url, "participating", "true")
        if member is not None:
            url = setQueryParameter(url, "member", member)

        LOG.info("Raw action electVote; url: " + url)
        return url

    def electVote(self, round: int, voter: str = None, candidate: str = None) -> str:
        """action: electVote"""
        assert isinstance(round, int), "round must be an integer"
        assert isinstance(voter, (str, type(None))), "voter must be a string or None"
        assert isinstance(candidate, (str, type(None))), "candidate must be a string or None"

        LOG.debug("ElectVote; round: " + str(round) +
                  "; voter: " + voter if voter is not None else "None" +
                  "; candidate: " + str(candidate) if candidate is not None else "None")

        url = setQueryParameter(self.baseUrl, "action", "electvote")
        url = setQueryParameter(url, "round", str(round))
        if voter is not None:
            url = setQueryParameter(url, "voter", voter)
        if candidate is not None:
            url = setQueryParameter(url, "candidate", candidate)

        LOG.info("Raw action electVote; url: " + url)
        return url

    def electvideo(self, round: int, voter: str = None) -> str:
        assert isinstance(round, int), "round must be an integer"
        assert isinstance(voter, str), "voter must be a string"

        LOG.debug("ElectVideo; round: " + str(round) +
                  "; voter: " + voter if voter is not None else "None")

        url = setQueryParameter(self.baseUrl, "action", "electvideo")
        url = setQueryParameter(url, "round", str(round))
        if voter is not None:
            url = setQueryParameter(url, "voter", voter)

        LOG.info("Raw action electvideo; url: " + url)
        return url

def main():
    test = 8


if __name__ == "__main__":
    main()