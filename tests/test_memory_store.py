from liya.memory_store import MemoryStore

def test_memory_extract_search_delete(tmp_path):
    store=MemoryStore(tmp_path/'memory.sqlite3')
    assert store.extract('Меня зовут Антон')
    facts=store.search('Антон')
    assert facts and 'Антон' in facts[0].content
    assert store.delete(facts[0].id)
    assert store.search('Антон') == []

def test_memory_is_deduplicated(tmp_path):
    store=MemoryStore(tmp_path/'memory.sqlite3')
    store.add('Пользователь предпочитает краткие ответы')
    store.add('Пользователь предпочитает краткие ответы')
    assert len(store.list()) == 1