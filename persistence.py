

import json
import os


class Log:
    def __init__(self, path="data.db"):
        self._path = path
        self._file = None

    def open_for_append(self):
        # "a" = append mode: writes go to the end, existing content is kept
        self._file = open(self._path, "a")

    def append(self, record):
        # record is a list like ["SET", "name", "roman"]
        self._file.write(json.dumps(record) + "\n")
        self._file.flush()          # hand it to the OS right away

    def replay(self, apply_function):
        if not os.path.exists(self._path):
            return                  # first run, nothing to replay
        with open(self._path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue        # skip a torn final line after a crash
                apply_function(record)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None