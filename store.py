from hashtable import HashTable

# the three kinds of things a key can hold
STRING = "string"
HASH = "hash"
LIST = "list"


class Value:
    """A stored value plus a tag saying what type it is."""

    def __init__(self, vtype, data):
        self.vtype = vtype   # "string", "hash", or "list"
        self.data = data     # a str, a HashTable, or a Python list


def new_string(text):
    return Value(STRING, text)


def new_hash():
    return Value(HASH, HashTable())   # reusing your own hash table!


def new_list():
    return Value(LIST, [])