import json
import os


class Log:
    def __init__(self, path="data.db"):
        self._path = path
        self._file = None

    def open_for_append(self):
        self._file = open(self._path, "a")

    def append(self, record):
        self._file.write(json.dumps(record) + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def replay(self, apply_function):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                apply_function(record)

    def close(self):
        if self._file is not None:
            self._file.close()
