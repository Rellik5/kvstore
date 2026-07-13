
from typing import List, Optional, Union

from hashtable import HashTable

# Type tags. A key holds exactly one of these kinds of value.
STRING = "string"
HASH = "hash"
LIST = "list"

# The concrete payload a Value can carry, one per type tag above.
Payload = Union[str, HashTable, List[str]]


class Value:
    """A stored value, tagged with its type and an optional expiry.

    Attributes:
        vtype: One of ``STRING``, ``HASH``, or ``LIST``.
        data: The payload -- a ``str``, a ``HashTable``, or a ``list``.
        expires_at: Absolute Unix timestamp at which the key dies, or
            None if it never expires. Storing an absolute deadline rather
            than a duration is what makes expiry survive a restart: a
            replayed log records *when* the key dies, not how long it had
            left when the command ran.
    """

    def __init__(
        self,
        vtype: str,
        data: Payload,
        expires_at: Optional[float] = None,
    ) -> None:
        self.vtype = vtype
        self.data = data
        self.expires_at = expires_at

    def clone(self) -> "Value":
        """Return an independent deep copy of this value.

        Transactions snapshot the whole store on BEGIN so that ABORT can
        restore it. A shallow copy would be useless: the snapshot would
        share the same underlying hash or list object, so writes made
        during the transaction would mutate the snapshot too and there
        would be nothing to roll back to.
        """
        if self.vtype == HASH:
            fields = HashTable()
            for field, field_value in self.data.items():
                fields.set(field, field_value)   # fields are plain strings
            return Value(HASH, fields, self.expires_at)

        if self.vtype == LIST:
            return Value(LIST, list(self.data), self.expires_at)

        return Value(STRING, self.data, self.expires_at)

    def __repr__(self) -> str:
        """Return a debugging representation naming the type and payload."""
        return "Value(%s, %r)" % (self.vtype, self.data)


def new_string(text: str) -> Value:
    """Create a value holding a plain string."""
    return Value(STRING, text)


def new_hash() -> Value:
    """Create an empty hash, whose fields live in their own HashTable."""
    return Value(HASH, HashTable())


def new_list() -> Value:
    """Create an empty ordered list."""
    return Value(LIST, [])


def is_type(item: Optional[Value], vtype: str) -> bool:
    """Return True if ``item`` exists and carries the given type tag."""
    return item is not None and item.vtype == vtype