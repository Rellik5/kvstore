

import sys
import time
from typing import List, Optional

from hashtable import HashTable
from persistence import Log, Record
from store import (
    HASH,
    LIST,
    STRING,
    Value,
    new_hash,
    new_list,
    new_string,
)

DB_PATH = "data.db"

# Responses. A missing key answers with an empty line; multi-line answers
# are terminated by END so a caller knows the reply is complete.
OK = "OK"
NIL = ""
END = "END"
ERR_TYPE = "ERR wrong type"
ERR_ARGS = "ERR wrong number of arguments"
ERR_INT = "ERR value is not an integer"
ERR_UNKNOWN = "ERR unknown command"
ERR_NO_TXN = "ERR no transaction in progress"
ERR_IN_TXN = "ERR already in a transaction"

MILLIS_PER_SECOND = 1000.0


def unquote(token: str) -> str:
    """Strip a matching pair of surrounding quotes from ``token``.

    A range query may be given an empty bound, written literally as ``""``,
    meaning "unbounded on this side".
    """
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


class Database:
    """The key-value store: an in-memory index backed by an append-only log.

    Writes are applied to the index and simultaneously recorded in the log,
    except while a transaction is open, when log records are buffered until
    the transaction commits.
    """

    def __init__(self, log: Log) -> None:
        self._index = HashTable()
        self._log = log

        # Transaction state. ``_snapshot`` is a deep copy of the index taken
        # at BEGIN so that ABORT can restore it; ``_buffer`` holds the log
        # records an open transaction has produced but not yet committed.
        self._in_transaction = False
        self._buffer: List[Record] = []
        self._snapshot: Optional[HashTable] = None

   
    def load(self) -> None:
        """Rebuild the index from the log, then discard expired keys."""
        self._log.replay(self._apply)
        for key in list(self._index.keys()):
            self._live(key)          # drops anything already past its expiry

    def _apply(self, record: Record) -> None:
        """Re-apply one logged record to memory during replay.

        This deliberately does not write to the log. Replay reconstructs
        history; recording it again would double the file on every restart.
        """
        action = record[0]

        if action == "SET":
            self._index.set(record[1], new_string(record[2]))

        elif action == "DEL":
            self._index.delete(record[1])

        elif action == "HSET":
            item = self._index.get(record[1])
            if item is None or item.vtype != HASH:
                item = new_hash()
                self._index.set(record[1], item)
            item.data.set(record[2], record[3])

        elif action in ("LPUSH", "RPUSH"):
            item = self._index.get(record[1])
            if item is None or item.vtype != LIST:
                item = new_list()
                self._index.set(record[1], item)
            if action == "LPUSH":
                item.data.insert(0, record[2])
            else:
                item.data.append(record[2])

        elif action in ("LPOP", "RPOP"):
            item = self._index.get(record[1])
            if item is not None and item.vtype == LIST and item.data:
                if action == "LPOP":
                    item.data.pop(0)
                else:
                    item.data.pop()

        elif action == "EXPIRE":
            item = self._index.get(record[1])
            if item is not None:
                item.expires_at = record[2]      # an absolute deadline

        elif action == "FLUSHDB":
            self._index.clear()

    
    def _live(self, key: str) -> Optional[Value]:
        """Look up a key, treating an expired one as though it were absent.

        Expiry is evaluated lazily rather than enforced by a background
        timer: a key is checked whenever it is touched, and dropped at that
        moment if its deadline has passed. Every read goes through here, so
        no command can ever observe a dead key.
        """
        item = self._index.get(key)
        if item is None:
            return None
        if item.expires_at is not None and time.time() >= item.expires_at:
            self._index.delete(key)
            return None
        return item

    def _record(self, record: Record) -> None:
        """Log a mutation, or buffer it if a transaction is open.

        Buffering is what keeps an aborted transaction out of the log
        entirely: if its writes had already been appended, replaying the
        log after a restart would silently reinstate the changes the abort
        was supposed to undo.
        """
        if self._in_transaction:
            self._buffer.append(record)
        else:
            self._log.append(record)

    
    def set(self, key: str, value: str) -> List[str]:
        """Store a string value, replacing anything previously held."""
        self._index.set(key, new_string(value))
        self._record(["SET", key, value])
        return [OK]

    def get(self, key: str) -> List[str]:
        """Return the string held at ``key``, or an empty reply if absent."""
        item = self._live(key)
        if item is None:
            return [NIL]
        if item.vtype != STRING:
            return [ERR_TYPE]
        return [item.data]

    def mset(self, pairs: List[str]) -> List[str]:
        """Set several keys at once from a flat key/value argument list."""
        if len(pairs) < 2 or len(pairs) % 2 != 0:
            return [ERR_ARGS]
        for position in range(0, len(pairs), 2):
            self.set(pairs[position], pairs[position + 1])
        return [OK]

    def mget(self, keys: List[str]) -> List[str]:
        """Return one line per key, empty for any that is missing."""
        lines = []
        for key in keys:
            item = self._live(key)
            if item is None or item.vtype != STRING:
                lines.append(NIL)
            else:
                lines.append(item.data)
        return lines

    def incr_by(self, key: str, delta: int) -> List[str]:
        """Add ``delta`` to a numeric key, treating a missing key as zero.

        Values are stored as text, so the current value is parsed, adjusted,
        and written back as text. A key holding something non-numeric is an
        error rather than a silent reset.
        """
        item = self._live(key)

        if item is None:
            current = 0                      # a missing counter starts at 0
        elif item.vtype != STRING:
            return [ERR_TYPE]
        else:
            try:
                current = int(item.data)
            except ValueError:
                return [ERR_INT]

        updated = str(current + delta)
        self._index.set(key, new_string(updated))
        # The *result* is logged, not the operation, so that replay stays
        # deterministic and never has to recompute anything.
        self._record(["SET", key, updated])
        return [updated]

    
    def delete(self, key: str) -> List[str]:
        """Remove a key, reporting 1 if one was removed and 0 otherwise."""
        if self._live(key) is not None and self._index.delete(key):
            self._record(["DEL", key])
            return ["1"]
        return ["0"]

    def exists(self, key: str) -> List[str]:
        """Report whether a live key is present."""
        return ["1" if self._live(key) is not None else "0"]

    def expire(self, key: str, millis: int) -> List[str]:
        """Give a key a time-to-live, measured in milliseconds.

        The deadline is stored as an absolute timestamp so that it keeps its
        original meaning when the log is replayed after a restart.
        """
        item = self._live(key)
        if item is None:
            return ["0"]
        deadline = time.time() + millis / MILLIS_PER_SECOND
        item.expires_at = deadline
        self._record(["EXPIRE", key, deadline])
        return ["1"]

    def ttl(self, key: str) -> List[str]:
        """Report the milliseconds a key has left.

        Returns -1 for a key that exists but never expires, and -2 for a key
        that does not exist at all, so the two cases stay distinguishable.
        """
        item = self._live(key)
        if item is None:
            return ["-2"]
        if item.expires_at is None:
            return ["-1"]
        remaining = int((item.expires_at - time.time()) * MILLIS_PER_SECOND)
        return [str(max(remaining, 0))]

    def key_range(self, start: str, end: str) -> List[str]:
        """Return the live keys falling between two bounds, sorted.

        Bounds are compared lexicographically and are inclusive. An empty
        bound means unbounded on that side. The reply always ends with END
        so a caller can tell an empty result from an unfinished one.
        """
        matches = []
        for key in list(self._index.keys()):
            if start and key < start:
                continue
            if end and key > end:
                continue
            if self._live(key) is not None:
                matches.append(key)
        return sorted(matches) + [END]

    
    def hset(self, key: str, field: str, value: str) -> List[str]:
        """Set a field inside a hash, creating the hash if it is new."""
        item = self._live(key)

        if item is None:
            item = new_hash()
            self._index.set(key, item)
        elif item.vtype != HASH:
            return [ERR_TYPE]

        item.data.set(field, value)          # item.data is itself a HashTable
        self._record(["HSET", key, field, value])
        return ["1"]

    def hget(self, key: str, field: str) -> List[str]:
        """Return one field of a hash, or an empty reply if it is absent."""
        item = self._live(key)
        if item is None:
            return [NIL]
        if item.vtype != HASH:
            return [ERR_TYPE]
        value = item.data.get(field)
        return [value if value is not None else NIL]

    def hgetall(self, key: str) -> List[str]:
        """Return every field of a hash as ``field value`` lines, then END."""
        item = self._live(key)
        if item is None:
            return [END]
        if item.vtype != HASH:
            return [ERR_TYPE]
        lines = ["%s %s" % (field, value) for field, value in item.data.items()]
        return lines + [END]

    
    def push(self, key: str, value: str, front: bool) -> List[str]:
        """Add a value to the front or back of a list, returning its length."""
        item = self._live(key)

        if item is None:
            item = new_list()
            self._index.set(key, item)
        elif item.vtype != LIST:
            return [ERR_TYPE]

        if front:
            item.data.insert(0, value)
        else:
            item.data.append(value)

        self._record(["LPUSH" if front else "RPUSH", key, value])
        return [str(len(item.data))]

    def pop(self, key: str, front: bool) -> List[str]:
        """Remove and return an element from the front or back of a list."""
        item = self._live(key)

        if item is None:
            return [NIL]
        if item.vtype != LIST:
            return [ERR_TYPE]
        if not item.data:
            return [NIL]

        value = item.data.pop(0) if front else item.data.pop()
        self._record(["LPOP" if front else "RPOP", key])
        return [value]

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        """Return a slice of a list, then END.

        Both ends are inclusive, and a negative index counts back from the
        end, so ``0 -1`` means the whole list. Out-of-range bounds are
        clamped rather than treated as errors.
        """
        item = self._live(key)
        if item is None:
            return [END]
        if item.vtype != LIST:
            return [ERR_TYPE]

        data = item.data
        length = len(data)

        if start < 0:
            start = max(length + start, 0)
        if stop < 0:
            stop = length + stop
        stop = min(stop, length - 1)

        if start >= length or start > stop:
            return [END]
        return list(data[start:stop + 1]) + [END]

    
    def flush(self) -> List[str]:
        """Delete every key in the database."""
        self._index.clear()
        self._record(["FLUSHDB"])
        return [OK]

    
    def begin(self) -> List[str]:
        """Open a transaction, snapshotting the index so ABORT can undo it.

        Each value is cloned rather than referenced, otherwise writes made
        during the transaction would mutate the snapshot as well and leave
        nothing to roll back to.
        """
        if self._in_transaction:
            return [ERR_IN_TXN]

        snapshot = HashTable()
        for key, item in self._index.items():
            snapshot.set(key, item.clone())

        self._snapshot = snapshot
        self._in_transaction = True
        self._buffer = []
        return [OK]

    def commit(self) -> List[str]:
        """Make the transaction permanent by flushing its buffered records."""
        if not self._in_transaction:
            return [ERR_NO_TXN]
        self._log.append_many(self._buffer)
        self._end_transaction()
        return [OK]

    def abort(self) -> List[str]:
        """Undo the transaction by restoring the snapshot and dropping writes."""
        if not self._in_transaction:
            return [ERR_NO_TXN]
        self._index = self._snapshot
        self._end_transaction()
        return [OK]

    def _end_transaction(self) -> None:
        """Clear the transaction state after a commit or abort."""
        self._in_transaction = False
        self._buffer = []
        self._snapshot = None


class Session:
    """Parses command lines and dispatches them to a :class:`Database`."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def execute(self, line: str) -> Optional[List[str]]:
        """Run one command line.

        Returns the lines to print, or None when the session should end.
        A malformed command produces an error reply rather than raising,
        so one bad line can never take down the whole session.
        """
        parts = line.split()
        if not parts:
            return []

        command = parts[0].upper()
        args = parts[1:]

        if command == "EXIT":
            return None

        try:
            return self._dispatch(command, args)
        except IndexError:
            return [ERR_ARGS]
        except ValueError:
            return [ERR_INT]

    def _dispatch(self, command: str, args: List[str]) -> List[str]:
        """Route a parsed command to the matching database operation."""
        database = self._db

        if command == "SET":
            return database.set(args[0], args[1])
        if command == "GET":
            return database.get(args[0])
        if command == "DEL":
            return database.delete(args[0])
        if command == "EXISTS":
            return database.exists(args[0])
        if command == "MSET":
            return database.mset(args)
        if command == "MGET":
            return database.mget(args) if args else [ERR_ARGS]
        if command == "INCR":
            return database.incr_by(args[0], 1)
        if command == "DECR":
            return database.incr_by(args[0], -1)
        if command == "EXPIRE":
            return database.expire(args[0], int(args[1]))
        if command == "TTL":
            return database.ttl(args[0])
        if command == "RANGE":
            return database.key_range(unquote(args[0]), unquote(args[1]))
        if command == "HSET":
            return database.hset(args[0], args[1], args[2])
        if command == "HGET":
            return database.hget(args[0], args[1])
        if command == "HGETALL":
            return database.hgetall(args[0])
        if command == "LPUSH":
            return database.push(args[0], args[1], front=True)
        if command == "RPUSH":
            return database.push(args[0], args[1], front=False)
        if command == "LPOP":
            return database.pop(args[0], front=True)
        if command == "RPOP":
            return database.pop(args[0], front=False)
        if command == "LRANGE":
            return database.lrange(args[0], int(args[1]), int(args[2]))
        if command == "FLUSHDB":
            return database.flush()
        if command == "BEGIN":
            return database.begin()
        if command == "COMMIT":
            return database.commit()
        if command == "ABORT":
            return database.abort()

        return [ERR_UNKNOWN]


def main() -> None:
    """Rebuild state from the log, then serve commands until end of input."""
    log = Log(DB_PATH)
    database = Database(log)
    database.load()             # replay history before accepting new writes
    log.open_for_append()

    session = Session(database)

    try:
        while True:
            # readline() returns as soon as a line arrives, unlike iterating
            # sys.stdin, which would buffer ahead and stall a waiting client.
            line = sys.stdin.readline()
            if line == "":                       # end of input
                break

            lines = session.execute(line.strip())
            if lines is None:                    # EXIT
                break

            for output in lines:
                sys.stdout.write(output + "\n")
            sys.stdout.flush()                   # let the caller see the reply
    finally:
        log.close()


if __name__ == "__main__":
    main()