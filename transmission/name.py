#
# Static functions for manipulating name/username for communication (and other) object
#


def ADD_AT_SIGN_IF_NOT_EXISTS(name: str) -> str:
    assert isinstance(name, str), "name must be a string"
    if name.startswith("@"):
        return name
    else:
        return "@" + name

def REMOVE_AT_SIGN_IF_EXISTS(name: (str, int)) -> (str, int):
    assert isinstance(name, (str, int)), "telegramID is not a string or int"
    if isinstance(name, int):
        return name
    else:
        if len(name) == 0:
            raise ValueError("REMOVE_AT_SIGN_IF_EXISTS; name type is string, but it is empty - zero length")
        if name[0] == "@":
            name = name[1:]
    return name

def PARSE_TG_NAME(name: str) -> str:
    assert isinstance(name, str), "name must be a string"
    prefix = "https://t.me/"
    if name.startswith(prefix):
        return ADD_AT_SIGN_IF_NOT_EXISTS(name=name[len(prefix):])
    else:
        return ADD_AT_SIGN_IF_NOT_EXISTS(name=name)