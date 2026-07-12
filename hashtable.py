class HashTable:
    def __init__(self):
        self._capacity = 8                        # how many boxes we have
        self._buckets = [None] * self._capacity   # the boxes, all empty for now

    def _hash(self, key):
        total = 0
        for ch in key:                 # go through each character in the key
            total = total + ord(ch)    # ord() = that character's number
        return total % self._capacity  # % keeps it inside 0..capacity-1

    def set(self, key, value):
        index = self._hash(key)
        bucket = self._buckets[index]
        if bucket is None:
            bucket = []
            self._buckets[index] = bucket
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value        # overwrite (last write wins)
                return
        bucket.append([key, value])

    def get(self, key):
        index = self._hash(key)
        bucket = self._buckets[index]
        if bucket is not None:
            for pair in bucket:
                if pair[0] == key:
                    return pair[1]
        return None

    def delete(self, key):
        index = self._hash(key)
        bucket = self._buckets[index]
        if bucket is not None:
            for i in range(len(bucket)):
                if bucket[i][0] == key:
                    bucket.pop(i)
                    return True
        return False

    def items(self):
        """Yield every (key, value) pair in the table."""
        for bucket in self._buckets:
            if bucket is not None:
                for pair in bucket:
                    yield pair[0], pair[1]

    def clear(self):
        """Remove everything."""
        self._buckets = [None] * self._capacity