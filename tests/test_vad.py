from liya.vad import EnergyVad, VadSession, pcm_energy

def test_energy_vad_endpoints():
    vad=EnergyVad(threshold=.02,min_silence_ms=100)
    assert not vad.push(.01,0).started
    assert vad.push(.1,50).started
    assert vad.push(0,100).duration_ms >= 50
    assert vad.push(0,150).ended

def test_energy_vad_max_duration():
    vad=EnergyVad(max_seconds=1)
    assert vad.push(.1,100).started
    assert not vad.push(.1,1001).ended
    assert vad.push(.1,1101).ended

def test_energy_vad_silence_uses_elapsed_time():
    vad=EnergyVad(threshold=.02,min_silence_ms=100)
    assert vad.push(.1,1000).started
    assert not vad.push(0,1050).ended
    assert vad.push(0,1100).ended

def test_pcm_energy_is_peak_sample():
    assert pcm_energy(b'') == 0.0
    assert pcm_energy(b'\x00') == 0.0
    assert pcm_energy(b'\x00\x00') == 0.0
    assert abs(pcm_energy(b'\xff\x7f') - 1.0) < 0.001
    assert pcm_energy(b'\x00\x00\xff\x7f') > 0.5

def _tracked_session(vad=None):
    session = VadSession(vad)
    clock = {"ms": 0.0}
    session.clock = lambda: clock["ms"] / 1000.0
    session.origin_ms = 0.0
    return session, clock

def test_vad_session_feeds_pcm_with_session_clock():
    session, clock = _tracked_session(EnergyVad(threshold=.02, min_silence_ms=100))
    loud = b'\xff\x7f' * 8
    quiet = b'\x00\x00' * 8
    assert session.feed_pcm(loud).started
    clock["ms"] = 50
    assert not session.feed_pcm(quiet).ended
    clock["ms"] = 200
    assert session.feed_pcm(quiet).ended

def test_vad_session_ignores_leading_silence():
    session, clock = _tracked_session(EnergyVad(threshold=.02, min_silence_ms=100))
    clock["ms"] = 5000
    result = session.feed_pcm(b'\x00\x00' * 8)
    assert not result.started
    assert not result.ended