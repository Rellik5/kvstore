"""A hand-written hash table used as the store's in-memory index.

The project requires that the index not rely on the language's built-in
dictionary/map types, so this module implements one from scratch.

Design
------
Storage is an array of *buckets* (a Python ``list``, which is a sequence
rather than an associative map, so it is permitted). A key is converted to
a bucket index by a hash function; because two different keys can hash to
the same index, each bucket holds a short list of ``[key, value]`` pairs
that is searched linearly. This strategy is called *separate chaining*.

The table doubles its capacity once it grows past a load factor of 0.75,
which keeps the average chain short and lookups close to O(1). Without
resizing, every operation would degrade toward O(n) as keys accumulated.
"""

from typing import Any, Iterator, List, Optional, Tuple

# A bucket is a list of [key, value] pairs; an empty bucket is None so that
# we only pay for a list once something actually hashes there.
Pair = List[Any]
Bucket = Optional[List[Pair]]


class HashTable:
    """A string-keyed hash table with separate chaining and resizing."""

    INITIAL_CAPACITY = 8
    MAX_LOAD_FACTOR = 0.75
    GROWTH_FACTOR = 2

    def __init__(self) -> None:
        self._capacity: int = self.INITIAL_CAPACITY
        self._size: int = 0
        self._buckets: List[Bucket] = [None] * self._capacity

    def _hash(self, key: str) -> int:
        """Map a key to a bucket index using the djb2 string hash.

        The multiply-and-add loop spreads similar keys across different
        buckets; masking to 32 bits keeps the intermediate value bounded,
        and the modulo folds the result into the current bucket range.
        """
        value = 5381
        for character in key:
            value = ((value * 33) + ord(character)) & 0xFFFFFFFF
        return value % self._capacity

    def set(self, key: str, value: Any) -> None:
        """Insert a key, or overwrite it if already present.

        Overwriting is what enforces the store's *last write wins* rule:
        the most recent value for a key replaces any earlier one.
        """
        index = self._hash(key)
        bucket = self._buckets[index]

        if bucket is None:
            bucket = []
            self._buckets[index] = bucket

        for pair in bucket:
            if pair[0] == key:
                pair[1] = value          # last write wins
                return

        bucket.append([key, value])
        self._size += 1

        if self._size / self._capacity > self.MAX_LOAD_FACTOR:
            self._resize()

    def get(self, key: str) -> Optional[Any]:
        """Return the value stored for ``key``, or None if absent."""
        bucket = self._buckets[self._hash(key)]
        if bucket is not None:
            for pair in bucket:
                if pair[0] == key:
                    return pair[1]
        return None

    def contains(self, key: str) -> bool:
        """Return True if ``key`` is present in the table."""
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        """Remove ``key``. Returns True only if a key was actually removed.

        The caller uses the return value to distinguish "deleted something"
        from "there was nothing to delete", which the DEL command reports
        as 1 and 0 respectively.
        """
        bucket = self._buckets[self._hash(key)]
        if bucket is not None:
            for position in range(len(bucket)):
                if bucket[position][0] == key:
                    bucket.pop(position)
                    self._size -= 1
                    return True
        return False

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Yield every ``(key, value)`` pair currently stored.

        Yields lazily rather than building a list, since callers such as
        RANGE only need to walk the pairs once.
        """
        for bucket in self._buckets:
            if bucket is not None:
                for pair in bucket:
                    yield pair[0], pair[1]

    def keys(self) -> Iterator[str]:
        """Yield every key currently stored."""
        for key, _ in self.items():
            yield key

    def clear(self) -> None:
        """Remove every entry, restoring the table to its initial state."""
        self._capacity = self.INITIAL_CAPACITY
        self._buckets = [None] * self._capacity
        self._size = 0

    def __len__(self) -> int:
        """Return the number of stored keys."""
        return self._size

    def _resize(self) -> None:
        """Grow the bucket array and re-hash every existing entry.

        Bucket indexes depend on the capacity, so entries cannot simply be
        copied across -- each one has to be hashed again into the larger
        array.
        """
        existing = list(self.items())
        self._capacity *= self.GROWTH_FACTOR
        self._buckets = [None] * self._capacity
        self._size = 0
        for key, value in existing:
            self.set(key, value)