#
# Static functions for manipulating name/username for communication object
#


def ADD_AT_SIGN_IF_NOT_EXISTS(name: str) -> str:
    assert isinstance(name, str), "name must be a string"
    if name.startswith("@"):
        return name
    else:
        return "@" + name