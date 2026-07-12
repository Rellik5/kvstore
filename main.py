import sys
from hashtable import HashTable
from persistence import Log
from store import new_string, STRING

store = HashTable()
log = Log("data.db")


def apply_record(record):
    """Re-apply one logged record to memory. Does NOT write to the log."""
    action = record[0]
    if action == "SET":
        store.set(record[1], new_string(record[2]))   # wrap it
    elif action == "DEL":
        store.delete(record[1])


log.replay(apply_record)
log.open_for_append()

for line in sys.stdin:
    line = line.rstrip("\n")
    parts = line.split()
    if not parts:
        continue

    command = parts[0].upper()

    if command == "SET":
        key = parts[1]
        value = parts[2]
        store.set(key, new_string(value))          # wrap before storing
        log.append(["SET", key, value])
        print("OK")

    elif command == "GET":
        key = parts[1]
        item = store.get(key)                      # this is a Value now, not a str
        if item is None:
            print("(nil)")
        elif item.vtype != STRING:                 # is it actually a string?
            print("ERR wrong type")
        else:
            print(item.data)                       # unwrap to get the text

    elif command == "DEL":
        key = parts[1]
        removed = store.delete(key)
        if removed:
            log.append(["DEL", key])
            print("1")
        else:
            print("0")

    elif command == "EXISTS":
        key = parts[1]
        if store.get(key) is None:
            print("0")
        else:
            print("1")

    elif command == "INCR" or command == "DECR":
        key = parts[1]
        item = store.get(key)

        if item is None:
            number = 0
        elif item.vtype != STRING:
            print("ERR wrong type")
            continue
        else:
            try:
                number = int(item.data)            # unwrap, then convert
            except ValueError:
                print("ERR value is not an integer")
                continue

        if command == "INCR":
            number = number + 1
        else:
            number = number - 1

        store.set(key, new_string(str(number)))    # wrap before storing
        log.append(["SET", key, str(number)])
        print(number)

    elif command == "EXIT":
        break

    else:
        print("ERR unknown command")

log.close()