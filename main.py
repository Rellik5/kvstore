import sys
from hashtable import HashTable
from persistence import Log

store = HashTable()
log = Log("data.db")


def apply_record(record):
    """Re-apply one logged record to memory. Does NOT write to the log."""
    action = record[0]
    if action == "SET":
        store.set(record[1], record[2])
    elif action == "DEL":
        store.delete(record[1])


log.replay(apply_record)   # rebuild state from last run
log.open_for_append()      # then start appending new writes

for line in sys.stdin:
    line = line.rstrip("\n")
    parts = line.split()
    if not parts:
        continue

    command = parts[0].upper()

    if command == "SET":
        key = parts[1]
        value = parts[2]
        store.set(key, value)
        log.append(["SET", key, value])      # <-- log it
        print("OK")

    elif command == "GET":
        key = parts[1]
        value = store.get(key)
        if value is None:
            print("(nil)")
        else:
            print(value)

    elif command == "DEL":
        key = parts[1]
        removed = store.delete(key)
        if removed:
            log.append(["DEL", key])         # <-- only log a real deletion
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
        current = store.get(key)

        if current is None:
            number = 0
        else:
            try:
                number = int(current)
            except ValueError:
                print("ERR value is not an integer")
                continue

        if command == "INCR":
            number = number + 1
        else:
            number = number - 1

        store.set(key, str(number))
        log.append(["SET", key, str(number)])   # <-- log the RESULT as a SET
        print(number)

    elif command == "EXIT":
        break

    else:
        print("ERR unknown command")

log.close()