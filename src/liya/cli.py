from __future__ import annotations
import argparse
import sys
import time
from .audio import NoAudio, energy_vad, write_wav
from pathlib import Path
from .clients import LocalClients, LocalServiceError
from .config import Settings
from .memory import ConversationStore
SYSTEM_PROMPT = "Ты — Лия, локальный голосовой компаньон. Отвечай тепло, естественно и кратко для голоса. Не выдумывай выполненные действия. Если не знаешь, скажи честно."
def build_parser():
    parser = argparse.ArgumentParser(prog="liya")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor"); sub.add_parser("chat")
    ask = sub.add_parser("ask"); ask.add_argument("text")
    say = sub.add_parser("say-file"); say.add_argument("audio")
    record = sub.add_parser("record", help="записать WAV с микрофона")
    record.add_argument("output", nargs="?", default="data/recording.wav")
    return parser
def main():
    args = build_parser().parse_args()
    try:
        settings = Settings.load(Path("config.json")); clients = LocalClients(settings)
    except (OSError, KeyError, ValueError) as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr); return 2
    if args.command == "doctor":
        for name, url in (("LLM", settings.llm_url), ("STT", settings.stt_url), ("TTS", settings.tts_url)): print(f"{name}: {url} — настройте локальный сервис")
        return 0
    store = ConversationStore("data/conversation.jsonl")
    def answer(text):
        reply = clients.chat([{"role":"system", "content":SYSTEM_PROMPT}, {"role":"user", "content":text}])
        store.add("user", text); store.add("assistant", reply); return reply
    if args.command == "record":
        try:
            import sounddevice as sd
            print("Говорите. Для завершения нажмите Enter.")
            with sd.InputStream(samplerate=32000, channels=1, dtype="int16") as stream:
                input("Нажмите Enter, когда закончите: ")
                frames = energy_vad(lambda n: stream.read(n // 2)[0].tobytes(), end=30.0)
            print(f"WAV: {write_wav(args.output, frames)}")
            return 0
        except (ImportError, OSError, RuntimeError) as exc:
            print(f"Микрофон недоступен: {exc}", file=sys.stderr); return 1
    if args.command == "ask":
        try: print(answer(args.text)); return 0
        except LocalServiceError as exc: print(str(exc), file=sys.stderr); return 1
    if args.command == "say-file":
        try:
            text = clients.transcribe(args.audio); reply = answer(text); output = clients.speak(reply)
            print(f"Вы: {text}\nЛия: {reply}\nАудио: {output}"); return 0
        except (LocalServiceError, OSError) as exc: print(str(exc), file=sys.stderr); return 1
    try:
        print("Лия слушает текстовый режим. Для выхода введите /exit")
        while True:
            text = input("Вы> ").strip()
            if text in {"/exit", "/quit"}: break
            if text:
                try: print(f"Лия> {answer(text)}")
                except LocalServiceError as exc: print(str(exc), file=sys.stderr)
    except (EOFError, KeyboardInterrupt): print()
    return 0
if __name__ == "__main__": raise SystemExit(main())
