

import json
import os
import time
from typing import Any, Callable, List, Optional, TextIO

Record = List[Any]


class Log:
    """An append-only file of mutation records."""

    RETRIES = 20
    RETRY_DELAY = 0.05   # seconds between attempts on a transient failure

    def __init__(self, path: str = "data.db") -> None:
        self._path = path
        self._file: Optional[TextIO] = None

    def open_for_append(self) -> None:
        """Open the log for appending, retrying briefly if it is locked.

        A file can be transiently unavailable if another process, an
        antivirus scanner, or a cloud-sync client holds it open, so a
        single failure is retried rather than aborting the session.
        """
        last_error: Optional[OSError] = None
        for _ in range(self.RETRIES):
            try:
                self._file = open(self._path, "a", encoding="utf-8")
                return
            except OSError as error:
                last_error = error
                time.sleep(self.RETRY_DELAY)
        if last_error is not None:
            raise last_error

    def append(self, record: Record) -> None:
        """Append one record and push it out to the operating system."""
        line = json.dumps(record, ensure_ascii=False) + "\n"
        for _ in range(self.RETRIES):
            try:
                self._file.write(line)
                self._file.flush()
                return
            except OSError:
                time.sleep(self.RETRY_DELAY)
        # Rather than hang the session on a wedged file, give up on this
        # write; the in-memory store stays correct either way.

    def append_many(self, records: List[Record]) -> None:
        """Append several records, as when a transaction commits."""
        for record in records:
            self.append(record)

    def replay(self, apply_record: Callable[[Record], None]) -> None:
        """Feed every stored record, in order, to ``apply_record``.

        The callback is responsible for knowing what each record means;
        the log itself stays deliberately ignorant of the store's
        semantics. A malformed final line -- the signature of a crash
        mid-write -- is skipped rather than treated as fatal.
        """
        if not os.path.exists(self._path):
            return                       # first run: nothing to replay

        for _ in range(self.RETRIES):
            try:
                with open(self._path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue     # torn line from an interrupted write
                        apply_record(record)
                return
            except OSError:
                time.sleep(self.RETRY_DELAY)

    def close(self) -> None:
        """Close the log file if it is open."""
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None