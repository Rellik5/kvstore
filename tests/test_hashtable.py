from hashtable import HashTable


def test_set_and_get():
    ht = HashTable()
    ht.set("a", 1)
    ht.set("b", 2)
    assert ht.get("a") == 1
    assert ht.get("b") == 2
    assert ht.get("missing") is None


def test_last_write_wins():
    ht = HashTable()
    ht.set("k", "first")
    ht.set("k", "second")
    assert ht.get("k") == "second"


def test_delete():
    ht = HashTable()
    ht.set("k", "v")
    assert ht.delete("k") is True
    assert ht.get("k") is None
    assert ht.delete("k") is False      # already gone


def test_collisions_are_handled():
    # "ab" and "ba" have the same character sum, so they hash to the
    # same bucket. This proves the chaining works.
    ht = HashTable()
    ht.set("ab", 1)
    ht.set("ba", 2)
    assert ht.get("ab") == 1
    assert ht.get("ba") == 2


def test_items_and_clear():
    ht = HashTable()
    ht.set("a", 1)
    ht.set("b", 2)
    assert len(list(ht.items())) == 2
    ht.clear()
    assert len(list(ht.items())) == 0