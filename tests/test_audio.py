import wave
from liya.audio import energy_vad, write_wav

def test_energy_vad_stops_after_silence():
    data = b'\x00\x00' * 3200 + b'\xff\x7f' * 16000 + b'\x00\x00' * 64000
    offset = 0
    def read(size):
        nonlocal offset
        result = data[offset:offset + size]
        offset += len(result)
        return result
    result = energy_vad(read, end=3.0)
    assert len(result) >= 16000
    assert len(result) < len(data)

def test_write_wav(tmp_path):
    path = write_wav(tmp_path / 'test.wav', b'\x00\x00' * 1600)
    with wave.open(str(path), 'rb') as stream:
        assert stream.getframerate() == 32000
        assert stream.getnframes() == 1600