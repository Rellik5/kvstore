import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "main.py")


def run(commands, cwd):
    """Pipe commands into main.py and return the output lines."""
    result = subprocess.run(
        [sys.executable, MAIN],
        input="\n".join(commands) + "\n",
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    return result.stdout.splitlines()


def test_set_and_get(tmp_path):
    assert run(["SET k v", "GET k", "EXIT"], tmp_path) == ["OK", "v"]


def test_missing_key(tmp_path):
    assert run(["GET nope", "EXIT"], tmp_path) == ["(nil)"]


def test_counters(tmp_path):
    assert run(["INCR n", "INCR n", "DECR n", "EXIT"], tmp_path) == ["1", "2", "1"]


def test_lists(tmp_path):
    out = run(["RPUSH l b", "LPUSH l a", "LRANGE l 0 -1", "EXIT"], tmp_path)
    assert out == ["1", "2", "a", "b"]


def test_hashes(tmp_path):
    assert run(["HSET h f v", "HGET h f", "EXIT"], tmp_path) == ["1", "v"]


def test_wrong_type_is_rejected(tmp_path):
    out = run(["SET s text", "LPUSH s x", "EXIT"], tmp_path)
    assert out == ["OK", "ERR wrong type"]


def test_persistence_across_restart(tmp_path):
    run(["SET durable yes", "EXIT"], tmp_path)          # first process
    assert run(["GET durable", "EXIT"], tmp_path) == ["yes"]   # second


def test_abort_rolls_back(tmp_path):
    run(["SET k original", "BEGIN", "SET k changed", "ABORT", "EXIT"], tmp_path)
    assert run(["GET k", "EXIT"], tmp_path) == ["original"]


def test_commit_persists(tmp_path):
    run(["BEGIN", "SET k saved", "COMMIT", "EXIT"], tmp_path)
    assert run(["GET k", "EXIT"], tmp_path) == ["saved"]
