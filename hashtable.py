class HashTable:
    def __init__(self):
        self._capacity = 8                        # how many boxes we have
        self._buckets = [None] * self._capacity   # the boxes, all empty for now

    def _hash(self, key):
        total = 0
        for ch in key:                # go through each character in the key
            total = total + ord(ch)   # ord() = that character's number
        return total % self._capacity # % keeps it inside 0..capacity-1

    def set(self, key, value):
        index = self._hash(key)          # which box?
        bucket = self._buckets[index]
        if bucket is None:               # box empty? make a fresh list
            bucket = []
            self._buckets[index] = bucket
        for pair in bucket:              # key already in this box?
            if pair[0] == key:
                pair[1] = value          # overwrite it (last write wins)
                return
        bucket.append([key, value])      # new key -> add the pair

    def get(self, key):
        index = self._hash(key)          # same formula -> same box
        bucket = self._buckets[index]
        if bucket is not None:
            for pair in bucket:          # scan the box for our key
                if pair[0] == key:
                    return pair[1]       # found it
        return None                      # not here

    def delete(self, key):
        index = self._hash(key)
        bucket = self._buckets[index]
        if bucket is not None:
            for i in range(len(bucket)):     # walk the box by position
                if bucket[i][0] == key:
                    bucket.pop(i)            # remove that pair
                    return True              # we deleted something
        return False                         # key wasn't there

    def items(self):
        """Yield every (key, value) pair in the table."""
        for bucket in self._buckets:
            if bucket is not None:
                for pair in bucket:
                    yield pair[0], pair[1]
    def clear(self):
        """Remove everything."""
        self._buckets = [None] * self._capacity