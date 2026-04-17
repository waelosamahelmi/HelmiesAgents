from helmiesagents.memory.store import MemoryStore


def test_memory_roundtrip(tmp_path):
    db = tmp_path / "mem.db"
    store = MemoryStore(str(db))

    store.add_message("s1", "user", "hello world")
    store.add_message("s1", "assistant", "hi there")

    hits = store.search_messages("hello")
    assert len(hits) == 1
    assert hits[0].content == "hello world"


def test_skill_save_get(tmp_path):
    db = tmp_path / "mem.db"
    store = MemoryStore(str(db))

    store.save_skill("deploy", "deployment flow", "step1 step2")
    sk = store.get_skill("deploy")

    assert sk is not None
    assert sk["name"] == "deploy"
