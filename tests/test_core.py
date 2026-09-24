from pathlib import Path
from liya.config import Settings
from liya.memory import ConversationStore
def test_settings_load(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text('{"llm_url":"l","stt_url":"s","tts_url":"t","model":"m","language":"ru","voice":"v","max_history_messages":2,"audio_output_path":"o.wav"}', encoding="utf-8")
    assert Settings.load(path).max_history_messages == 2
def test_store(tmp_path: Path):
    store = ConversationStore(tmp_path / "history.jsonl"); store.add("user", "привет"); store.add("assistant", "здравствуй")
    assert store.load()[1]["content"] == "здравствуй"
