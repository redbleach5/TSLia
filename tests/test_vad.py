from liya.vad import EnergyVad

def test_energy_vad_endpoints():
    vad=EnergyVad(threshold=.02,min_silence_ms=100)
    assert not vad.push(.01,0).started
    assert vad.push(.1,50).started
    assert vad.push(0,100).duration_ms >= 50
    assert vad.push(0,150).ended

def test_energy_vad_max_duration():
    vad=EnergyVad(max_seconds=1)
    assert vad.push(.1,100).started
    assert vad.push(.1,1001).ended