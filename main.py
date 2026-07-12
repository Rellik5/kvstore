import sys
import time
from hashtable import HashTable
from persistence import Log
from store import new_string, new_hash, new_list, STRING, HASH, LIST

store = HashTable()
log = Log("data.db")


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


log.replay(apply_record)       # rebuild state from last run

for key, item in list(store.items()):
    get_live(key)              # drop anything that already expired

log.open_for_append()          # then start appending new writes

for line in sys.stdin:
    line = line.rstrip("\n")
    parts = line.split()
    if not parts:
        continue

    command = parts[0].upper()

    if command == "SET":
        key = parts[1]
        value = parts[2]
        store.set(key, new_string(value))
        log.append(["SET", key, value])
        print("OK")

    elif command == "GET":
        key = parts[1]
        item = get_live(key)
        if item is None:
            print("(nil)")
        elif item.vtype != STRING:
            print("ERR wrong type")
        else:
            print(item.data)

    elif command == "DEL":
        key = parts[1]
        if get_live(key) is not None and store.delete(key):
            log.append(["DEL", key])
            print("1")
        else:
            print("0")

    elif command == "EXISTS":
        key = parts[1]
        if get_live(key) is None:
            print("0")
        else:
            print("1")

    elif command == "MSET":
        if len(parts) < 3 or len(parts) % 2 == 0:
            print("ERR wrong number of arguments")
            continue
        i = 1
        while i < len(parts):
            key = parts[i]
            value = parts[i + 1]
            store.set(key, new_string(value))
            log.append(["SET", key, value])
            i = i + 2
        print("OK")

    elif command == "MGET":
        for key in parts[1:]:
            item = get_live(key)
            if item is None or item.vtype != STRING:
                print("(nil)")
            else:
                print(item.data)

    elif command == "INCR" or command == "DECR":
        key = parts[1]
        item = get_live(key)

        if item is None:
            number = 0
        elif item.vtype != STRING:
            print("ERR wrong type")
            continue
        else:
            try:
                number = int(item.data)
            except ValueError:
                print("ERR value is not an integer")
                continue

        if command == "INCR":
            number = number + 1
        else:
            number = number - 1

        store.set(key, new_string(str(number)))
        log.append(["SET", key, str(number)])
        print(number)

    elif command == "EXPIRE":
        key = parts[1]
        seconds = int(parts[2])
        item = get_live(key)
        if item is None:
            print("0")
        else:
            deadline = time.time() + seconds   # absolute time it dies
            item.expires_at = deadline
            log.append(["EXPIRE", key, deadline])
            print("1")

    elif command == "TTL":
        key = parts[1]
        item = get_live(key)
        if item is None:
            print("-2")                        # no such key
        elif item.expires_at is None:
            print("-1")                        # exists, never expires
        else:
            remaining = int(item.expires_at - time.time())
            if remaining < 0:
                remaining = 0
            print(remaining)

    elif command == "RANGE":
        start = parts[1]
        end = parts[2]
        matches = []
        for key, item in list(store.items()):
            if start <= key <= end:
                if get_live(key) is not None:
                    matches.append(key)
        if not matches:
            print("(empty)")
        else:
            for key in sorted(matches):
                print(key)

    elif command == "HSET":
        key = parts[1]
        field = parts[2]
        value = parts[3]
        item = get_live(key)

        if item is None:
            item = new_hash()
            store.set(key, item)
        elif item.vtype != HASH:
            print("ERR wrong type")
            continue

        item.data.set(field, value)
        log.append(["HSET", key, field, value])
        print("1")

    elif command == "HGET":
        key = parts[1]
        field = parts[2]
        item = get_live(key)

        if item is None:
            print("(nil)")
        elif item.vtype != HASH:
            print("ERR wrong type")
        else:
            value = item.data.get(field)
            if value is None:
                print("(nil)")
            else:
                print(value)

    elif command == "HGETALL":
        key = parts[1]
        item = get_live(key)

        if item is None:
            print("(empty)")
        elif item.vtype != HASH:
            print("ERR wrong type")
        else:
            found = False
            for field, value in item.data.items():
                print(field + ": " + value)
                found = True
            if not found:
                print("(empty)")

    elif command == "LPUSH" or command == "RPUSH":
        key = parts[1]
        value = parts[2]
        item = get_live(key)

        if item is None:
            item = new_list()
            store.set(key, item)
        elif item.vtype != LIST:
            print("ERR wrong type")
            continue

        if command == "LPUSH":
            item.data.insert(0, value)   # position 0 = the front
        else:
            item.data.append(value)      # append = the back

        log.append([command, key, value])
        print(len(item.data))

    elif command == "LRANGE":
        key = parts[1]
        start = int(parts[2])
        stop = int(parts[3])
        item = get_live(key)

        if item is None:
            print("(empty)")
        elif item.vtype != LIST:
            print("ERR wrong type")
        else:
            data = item.data
            n = len(data)

            if start < 0:                # -1 means "last"
                start = n + start
                if start < 0:
                    start = 0
            if stop < 0:
                stop = n + stop

            if start >= n or start > stop:
                print("(empty)")
            else:
                if stop > n - 1:
                    stop = n - 1
                for i in range(start, stop + 1):   # stop is inclusive
                    print(data[i])

    elif command == "FLUSHDB":
        store.clear()
        log.append(["FLUSHDB"])
        print("OK")

    elif command == "EXIT":
        break

    else:
        print("ERR unknown command")

log.close()