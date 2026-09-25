import sys
import types
import pytest
from liya.silero_vad import SileroScorer, load_silero_scorer
from liya.vad import EnergyVad, VadSession, pcm_energy

NP = pytest.importorskip('numpy')

class FakeMeta:
    def __init__(self,name,type='tensor(float)',shape=None): self.name=name; self.type=type; self.shape=[1,'N'] if shape is None else shape

class FakeSession:
    """Подмена onnxruntime InferenceSession: фиксированные метаданные и вероятность."""
    def __init__(self,probability=0.9,with_state=True):
        self.probability=probability; self.with_state=with_state; self.feeds=[]
    def get_inputs(self):
        inputs=[FakeMeta('input'),FakeMeta('sr',type='tensor(int64)',shape=[])]
        return inputs+[FakeMeta('state',shape=[2,1,64])] if self.with_state else inputs
    def get_outputs(self):
        outputs=[FakeMeta('output')]
        return outputs+[FakeMeta('stateN',shape=[2,1,64])] if self.with_state else outputs
    def run(self,outputs,feed):
        self.feeds.append(dict(feed))
        probability=self.probability.pop(0) if isinstance(self.probability,list) else self.probability
        produced=[NP.array([[probability]],dtype=NP.float32)]
        if self.with_state: produced.append(NP.ones((2,1,64),dtype=NP.float32))
        return produced

class BrokenSession(FakeSession):
    def run(self,outputs,feed): raise RuntimeError('onnx runtime failure')

class OrtSession(FakeSession):
    def __init__(self,path,sess_options=None,providers=None): FakeSession.__init__(self,probability=0.6)

class BrokenOrtSession(BrokenSession):
    def __init__(self,path,sess_options=None,providers=None): BrokenSession.__init__(self)

def _fake_onnxruntime(session_class):
    options=type('SessionOptions',(),{'intra_op_num_threads':0,'inter_op_num_threads':0})
    return type('FakeOrt',(),{'SessionOptions':options,'InferenceSession':session_class})

def _tracked(vad, scorer=None, fallback_threshold=None):
    session=VadSession(vad, scorer=scorer, fallback_threshold=fallback_threshold)
    clock={'ms':0.0}
    session.clock=lambda: clock['ms']/1000.0
    session.origin_ms=0.0
    return session, clock

def test_load_returns_none_without_model_file(tmp_path):
    assert load_silero_scorer(tmp_path/'missing.onnx') is None

def test_load_builds_scorer_through_onnxruntime(monkeypatch, tmp_path):
    model=tmp_path/'silero_vad.onnx'; model.write_bytes(b'onnx')
    monkeypatch.setitem(sys.modules,'onnxruntime',_fake_onnxruntime(OrtSession))
    scorer=load_silero_scorer(model, threshold=0.5, source_rate=16000)
    assert scorer is not None and scorer.backend == 'silero'
    assert scorer.detect(b'\x00\x00'*512).confidence == pytest.approx(0.6)

def test_load_returns_none_when_model_contract_fails(monkeypatch, tmp_path):
    model=tmp_path/'silero_vad.onnx'; model.write_bytes(b'onnx')
    monkeypatch.setitem(sys.modules,'onnxruntime',_fake_onnxruntime(BrokenOrtSession))
    assert load_silero_scorer(model, source_rate=16000) is None

def test_session_is_cached_between_scorers(monkeypatch, tmp_path):
    model=tmp_path/'silero_vad.onnx'; model.write_bytes(b'onnx')
    opened=[]
    class CountingOrtSession(OrtSession):
        def __init__(self,path,sess_options=None,providers=None): opened.append(path); OrtSession.__init__(self,path)
    monkeypatch.setitem(sys.modules,'onnxruntime',_fake_onnxruntime(CountingOrtSession))
    first=load_silero_scorer(model, source_rate=16000)
    second=load_silero_scorer(model, source_rate=16000)
    assert opened == [str(model)]
    assert first is not second and first.session is second.session

def test_unavailable_reason_explains_energy_fallback(monkeypatch, tmp_path):
    from liya.silero_vad import silero_unavailable_reason
    missing=tmp_path/'none.onnx'
    assert silero_unavailable_reason(missing) == f'нет файла {missing}'
    model=tmp_path/'silero_vad.onnx'; model.write_bytes(b'onnx')
    monkeypatch.setitem(sys.modules,'onnxruntime',_fake_onnxruntime(OrtSession))
    assert silero_unavailable_reason(model) is None
    broken=tmp_path/'broken.onnx'; broken.write_bytes(b'onnx')
    monkeypatch.setitem(sys.modules,'onnxruntime',_fake_onnxruntime(BrokenOrtSession))
    assert silero_unavailable_reason(broken) == 'контракт модели не подошёл'

def test_scorer_buffers_frames_and_downsamples_32k_to_16k():
    session=FakeSession(probability=0.75); scorer=SileroScorer(session, source_rate=32000, threshold=0.5)
    frame=b'\x10\x00'*1024
    assert scorer.frame_bytes == 2048 and scorer.factor == 2
    assert scorer.score(frame[:1024]) == 0.0
    assert session.feeds == []
    assert scorer.score(frame[1024:]) == pytest.approx(0.75)
    assert int(session.feeds[0]['sr']) == 16000
    assert session.feeds[0]['input'].shape == (1,512)
    assert session.feeds[0]['state'].shape == (2,1,64)

def test_scorer_returns_best_probability_inside_chunk():
    session=FakeSession(probability=[0.1,0.9]); scorer=SileroScorer(session, source_rate=16000, threshold=0.5)
    assert scorer.score(b'\x00\x00'*1024) == pytest.approx(0.9)
    assert len(session.feeds) == 2

def test_scorer_keeps_state_between_chunks_and_resets():
    session=FakeSession(probability=0.2); scorer=SileroScorer(session, source_rate=16000, threshold=0.5)
    frame=b'\x00\x00'*512
    result=scorer.detect(frame)
    assert result.is_speech is False and result.confidence == pytest.approx(0.2)
    assert NP.all(session.feeds[0]['state'] == 0)
    scorer.detect(frame)
    assert NP.all(session.feeds[1]['state'] == 1)
    scorer.reset()
    scorer.detect(frame)
    assert NP.all(session.feeds[2]['state'] == 0)
    assert scorer.using_fallback is False

def test_scorer_switches_to_energy_after_repeated_errors():
    scorer=SileroScorer(BrokenSession(), source_rate=32000, threshold=0.5, max_errors=2)
    loud=b'\xff\x7f'*1024
    assert scorer.score(loud) == pytest.approx(0.0)
    assert scorer.using_fallback is False
    assert scorer.score(loud) == pytest.approx(pcm_energy(loud))
    assert scorer.using_fallback is True

def test_vad_session_uses_silero_probability():
    session=FakeSession(probability=0.9); scorer=SileroScorer(session, source_rate=16000, threshold=0.5)
    tracked, clock = _tracked(EnergyVad(threshold=0.5, min_silence_ms=100), scorer=scorer, fallback_threshold=0.025)
    frame=b'\x01\x00'*512
    assert tracked.backend == 'silero'
    assert tracked.feed_pcm(frame).started
    session.probability=0.1
    clock['ms']=50
    assert not tracked.feed_pcm(frame).ended
    clock['ms']=200
    assert tracked.feed_pcm(frame).ended

def test_vad_session_returns_to_energy_threshold_after_fallback():
    scorer=SileroScorer(BrokenSession(), source_rate=32000, threshold=0.5, max_errors=1)
    tracked, _ = _tracked(EnergyVad(threshold=0.5, min_silence_ms=100), scorer=scorer, fallback_threshold=0.025)
    quiet_speech=(1000).to_bytes(2,'little',signed=True)*1024
    assert tracked.feed_pcm(quiet_speech).started
    assert tracked.backend == 'energy (fallback)'
    assert tracked.vad.threshold == pytest.approx(0.025)

def test_from_settings_keeps_energy_when_silero_unavailable(tmp_path):
    base={'vad_threshold':0.025,'vad_min_speech_ms':300,'vad_min_silence_ms':850,'vad_max_seconds':30}
    energy=VadSession.from_settings(types.SimpleNamespace(**base))
    assert energy.backend == 'energy' and energy.vad.threshold == pytest.approx(0.025)
    silero=VadSession.from_settings(types.SimpleNamespace(**base, vad_backend='silero', vad_model_path=str(tmp_path/'none.onnx'), vad_silero_threshold=0.5))
    assert silero.backend == 'energy' and silero.vad.threshold == pytest.approx(0.025)
    assert VadSession.from_settings(None).backend == 'energy'
