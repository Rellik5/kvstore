from store import new_string, new_hash, new_list, STRING, HASH, LIST


def test_string_value():
    v = new_string("roman")
    assert v.vtype == STRING
    assert v.data == "roman"
    assert v.expires_at is None


def test_hash_value_holds_a_hashtable():
    v = new_hash()
    assert v.vtype == HASH
    v.data.set("city", "denton")
    assert v.data.get("city") == "denton"


def test_list_value():
    v = new_list()
    assert v.vtype == LIST
    v.data.append("x")
    assert v.data == ["x"]


def test_clone_is_a_deep_copy():
    original = new_list()
    original.data.append("a")
    copy = original.clone()
    original.data.append("b")      # change the original AFTER cloning
    assert copy.data == ["a"]      # the copy must NOT have changed