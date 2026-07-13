

import json
import os
import time


class Log:
    _RETRIES = 20
    _RETRY_DELAY = 0.05   # seconds

    def __init__(self, path="data.db"):
        self._path = path
        self._file = None

    def open_for_append(self):
        """Open in append mode, retrying briefly if the file is locked."""
        last_error = None
        for _ in range(self._RETRIES):
            try:
                self._file = open(self._path, "a")
                return
            except OSError as exc:
                last_error = exc
                time.sleep(self._RETRY_DELAY)
        raise last_error

    def append(self, record):
        """Append one record (a list) and push it to the OS immediately."""
        line = json.dumps(record) + "\n"
        for _ in range(self._RETRIES):
            try:
                self._file.write(line)
                self._file.flush()
                return
            except OSError:
                time.sleep(self._RETRY_DELAY)
        # Give up on disk rather than hang the session; memory stays correct.

    def replay(self, apply_function):
        """Feed every stored record, in order, to ``apply_function``."""
        if not os.path.exists(self._path):
            return                  # first run, nothing to replay
        for _ in range(self._RETRIES):
            try:
                with open(self._path, "r") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue   # skip a torn line after a crash
                        apply_function(record)
                return
            except OSError:
                time.sleep(self._RETRY_DELAY)

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
