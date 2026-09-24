import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 32_000
SAMPLE_WIDTH = 2
CHANNELS = 1
MIN_SPEECH_SEC = 0.2
ENERGY_THRESHOLD = 0.01
SILENCE_SECONDS = 0.6
MAX_SECONDS = 30.0

class UserAudioUnavailable(RuntimeError):
    pass

@dataclass
class NoAudio:
    sample_rate: int = SAMPLE_RATE
    sample_width: int = SAMPLE_WIDTH
    channels: int = CHANNELS

    def read(self, frames: int) -> bytes:
        import time
        time.sleep(frames / self.sample_rate)
        return b'\x00' * (frames * self.sample_width * self.channels)

def energy_vad(read, start: float | None = None, end: float | None = None):
    start = 0.0 if start is None else start
    end = MAX_SECONDS if end is None else min(end, MAX_SECONDS)
    frames = int((end - start) * SAMPLE_RATE)
    chunk = int(0.1 * SAMPLE_RATE)
    chunk_bytes = chunk * SAMPLE_WIDTH * CHANNELS
    silence = 0.0
    speech_started = False
    samples = bytearray()
    for _ in range(0, frames, chunk):
        data = read(chunk_bytes)
        if not data:
            break
        samples.extend(data)
        energy = max(abs(int.from_bytes(data[i:i + 2], "little", signed=True)) for i in range(0, len(data) - 1, 2)) / 32768.0 if data else 0.0
        if energy >= ENERGY_THRESHOLD:
            speech_started = True
            silence = 0.0
        elif speech_started:
            silence += chunk / SAMPLE_RATE
            if silence >= SILENCE_SECONDS:
                break
    return bytes(samples)

def write_wav(path: str | Path, audio: bytes, sample_rate: int = SAMPLE_RATE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(SAMPLE_WIDTH)
        output.setframerate(sample_rate)
        output.writeframes(audio)
    return path