"""Simple persistent key-value store.

Reads one command per line from STDIN and writes results to STDOUT, so it
works interactively and when driven by an automated black-box tester.

Two details matter for interactive clients:

* Input is read with ``sys.stdin.readline()`` rather than ``for line in
  sys.stdin``. Iterating the file object uses an internal read-ahead
  buffer, so Python will not hand us the first line until it has read a
  large chunk or seen EOF -- a client that writes one command and waits
  for a reply would hang forever.
* Every response is flushed immediately. When stdout is a pipe, Python
  buffers it by default, so a waiting client would never see the reply.
"""

import sys
import time

from hashtable import HashTable
from persistence import Log
from store import new_string, new_hash, new_list, STRING, HASH, LIST

store = HashTable()
log = Log("data.db")

in_transaction = False
txn_buffer = []      # log records waiting to be committed
snapshot = None      # copy of the store, for rollback


def out(text):
    """Write one response line and flush it immediately."""
    sys.stdout.write(str(text) + "\n")
    sys.stdout.flush()


def apply_record(record):
    """Re-apply one logged record to memory. Does NOT write to the log."""
    action = record[0]
    if action == "SET":
        store.set(record[1], new_string(record[2]))
    elif action == "DEL":
        store.delete(record[1])
    elif action == "HSET":
        item = store.get(record[1])
        if item is None or item.vtype != HASH:
            item = new_hash()
            store.set(record[1], item)
        item.data.set(record[2], record[3])
    elif action == "LPUSH" or action == "RPUSH":
        item = store.get(record[1])
        if item is None or item.vtype != LIST:
            item = new_list()
            store.set(record[1], item)
        if action == "LPUSH":
            item.data.insert(0, record[2])
        else:
            item.data.append(record[2])
    elif action == "EXPIRE":
        item = store.get(record[1])
        if item is not None:
            item.expires_at = record[2]
    elif action == "FLUSHDB":
        store.clear()


def get_live(key):
    """Get a key, treating expired keys as if they don't exist."""
    item = store.get(key)
    if item is None:
        return None
    if item.expires_at is not None and time.time() >= item.expires_at:
        store.delete(key)      # it's dead -- clean it up now
        return None
    return item


def write_log(record):
    """Log a change -- or buffer it if we're inside a transaction."""
    if in_transaction:
        txn_buffer.append(record)
    else:
        log.append(record)


def handle(parts):
    """Run one parsed command. Returns False when the program should stop."""
    global in_transaction, txn_buffer, snapshot, store

    command = parts[0].upper()

    if command == "EXIT":
        return False

    elif command == "SET":
        key = parts[1]
        value = parts[2]
        store.set(key, new_string(value))
        write_log(["SET", key, value])
        out("OK")

    elif command == "GET":
        key = parts[1]
        item = get_live(key)
        if item is None:
            out("")                            # missing key -> empty response
        elif item.vtype != STRING:
            out("ERR wrong type")
        else:
            out(item.data)

    elif command == "DEL":
        key = parts[1]
        if get_live(key) is not None and store.delete(key):
            write_log(["DEL", key])
            out("1")
        else:
            out("0")

    elif command == "EXISTS":
        key = parts[1]
        if get_live(key) is None:
            out("0")
        else:
            out("1")

    elif command == "MSET":
        if len(parts) < 3 or len(parts) % 2 == 0:
            out("ERR wrong number of arguments")
            return True
        i = 1
        while i < len(parts):
            store.set(parts[i], new_string(parts[i + 1]))
            write_log(["SET", parts[i], parts[i + 1]])
            i = i + 2
        out("OK")

    elif command == "MGET":
        for key in parts[1:]:
            item = get_live(key)
            if item is None or item.vtype != STRING:
                out("")                        # missing key -> empty response
            else:
                out(item.data)

    elif command == "INCR" or command == "DECR":
        key = parts[1]
        item = get_live(key)

        if item is None:
            number = 0
        elif item.vtype != STRING:
            out("ERR wrong type")
            return True
        else:
            try:
                number = int(item.data)
            except ValueError:
                out("ERR value is not an integer")
                return True

        if command == "INCR":
            number = number + 1
        else:
            number = number - 1

        store.set(key, new_string(str(number)))
        write_log(["SET", key, str(number)])
        out(number)

    elif command == "EXPIRE":
        key = parts[1]
        seconds = int(parts[2])
        item = get_live(key)
        if item is None:
            out("0")
        else:
            deadline = time.time() + seconds   # absolute time it dies
            item.expires_at = deadline
            write_log(["EXPIRE", key, deadline])
            out("1")

    elif command == "TTL":
        key = parts[1]
        item = get_live(key)
        if item is None:
            out("-2")                          # no such key
        elif item.expires_at is None:
            out("-1")                          # exists, never expires
        else:
            remaining = int(item.expires_at - time.time())
            if remaining < 0:
                remaining = 0
            out(remaining)

    elif command == "RANGE":
        start = parts[1]
        end = parts[2]
        matches = []
        for key, item in list(store.items()):
            if start <= key <= end and get_live(key) is not None:
                matches.append(key)
        for key in sorted(matches):
            out(key)
        out("END")                             # terminates the key list

    elif command == "HSET":
        key = parts[1]
        field = parts[2]
        value = parts[3]
        item = get_live(key)

        if item is None:
            item = new_hash()                  # first field -- create it
            store.set(key, item)
        elif item.vtype != HASH:
            out("ERR wrong type")
            return True

        item.data.set(field, value)            # item.data IS a HashTable
        write_log(["HSET", key, field, value])
        out("1")

    elif command == "HGET":
        key = parts[1]
        field = parts[2]
        item = get_live(key)

        if item is None:
            out("")                            # missing key -> empty response
        elif item.vtype != HASH:
            out("ERR wrong type")
        else:
            value = item.data.get(field)
            out(value if value is not None else "")

    elif command == "HGETALL":
        key = parts[1]
        item = get_live(key)

        if item is None:
            out("END")
        elif item.vtype != HASH:
            out("ERR wrong type")
        else:
            for field, value in item.data.items():
                out(field + " " + value)
            out("END")

    elif command == "LPUSH" or command == "RPUSH":
        key = parts[1]
        value = parts[2]
        item = get_live(key)

        if item is None:
            item = new_list()                  # first push -- create it
            store.set(key, item)
        elif item.vtype != LIST:
            out("ERR wrong type")
            return True

        if command == "LPUSH":
            item.data.insert(0, value)         # position 0 = the front
        else:
            item.data.append(value)            # append = the back

        write_log([command, key, value])
        out(len(item.data))

    elif command == "LRANGE":
        key = parts[1]
        start = int(parts[2])
        stop = int(parts[3])
        item = get_live(key)

        if item is None:
            out("END")
        elif item.vtype != LIST:
            out("ERR wrong type")
        else:
            data = item.data
            n = len(data)

            if start < 0:                      # -1 means "last"
                start = max(n + start, 0)
            if stop < 0:
                stop = n + stop
            if stop > n - 1:
                stop = n - 1

            if start < n and start <= stop:
                for i in range(start, stop + 1):   # stop is inclusive
                    out(data[i])
            out("END")

    elif command == "FLUSHDB":
        store.clear()
        write_log(["FLUSHDB"])
        out("OK")

    elif command == "BEGIN":
        if in_transaction:
            out("ERR already in a transaction")
        else:
            snapshot = HashTable()
            for key, item in store.items():
                snapshot.set(key, item.clone())    # deep copy every value
            in_transaction = True
            txn_buffer = []
            out("OK")

    elif command == "COMMIT":
        if not in_transaction:
            out("ERR no transaction in progress")
        else:
            for record in txn_buffer:          # NOW write them to disk
                log.append(record)
            in_transaction = False
            txn_buffer = []
            snapshot = None
            out("OK")

    elif command == "ABORT":
        if not in_transaction:
            out("ERR no transaction in progress")
        else:
            store = snapshot                   # restore the old state
            in_transaction = False
            txn_buffer = []                    # discard buffered writes
            snapshot = None
            out("OK")

    else:
        out("ERR unknown command")

    return True


def main():
    log.replay(apply_record)           # rebuild state from last run

    for key, item in list(store.items()):
        get_live(key)                  # drop anything already expired

    log.open_for_append()              # then start appending new writes

    while True:
        line = sys.stdin.readline()    # one line at a time, no read-ahead
        if line == "":                 # empty string means EOF
            break

        parts = line.strip().split()
        if not parts:
            continue

        try:
            if not handle(parts):      # EXIT returns False
                break
        except IndexError:
            out("ERR wrong number of arguments")
        except ValueError:
            out("ERR invalid argument")

    log.close()


if __name__ == "__main__":
    main()