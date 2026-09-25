import asyncio, json
from pathlib import Path
from liya.clients import LocalClients
from liya.config import Settings
from liya.latency import LatencyLog, percentile
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self,event): self.events.append(event)

class FakeClients(LocalClients):
    def transcribe_with_confidence(self,path): return 'тест', 1.0
    def transcribe(self,path): return 'тест'
    def chat(self,messages): return 'Ок'
    def speak(self,text,output_path=None):
        path=Path(output_path or 'o.wav'); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'RIFF'); return path

def _events(ws): return [json.loads(item) for item in ws.events]

def test_percentile_nearest_rank():
    assert percentile([], .95) == 0.0
    assert percentile([10], .95) == 10
    assert percentile([10,20,30,40], .5) == 20
    assert percentile([10,20,30,40], .95) == 40
    assert percentile([1,2,3], 2.0) == 3

def test_latency_log_reports_p50_p95():
    log=LatencyLog(window=20)
    for value in range(1,11): log.record('stt', value)
    stats=log.stats()['stt']
    assert stats == {'count':10,'p50':5.0,'p95':10.0,'min':1.0,'max':10.0}
    assert log.p50('stt') == 5.0 and log.p95('stt') == 10.0

def test_latency_log_keeps_only_window():
    log=LatencyLog(window=3)
    for value in (100,200,300,400): log.record('total', value)
    assert log.samples('total') == [200.0,300.0,400.0]

def test_latency_log_ignores_invalid_samples():
    log=LatencyLog()
    log.record('llm', -5); log.record('llm', float('nan')); log.record('llm', float('inf')); log.record('llm', None)
    assert log.samples('llm') == []
    assert log.stats() == {}

def test_latency_log_regression_needs_budget_and_evidence():
    log=LatencyLog(window=20, budget_ms=1000, min_samples=5)
    for _ in range(4): log.record('total', 5000)
    assert log.regressed() == []
    log.record('total', 5000)
    assert log.regressed() == ['total']
    assert LatencyLog(budget_ms=0).regressed() == []

def test_latency_log_reset():
    log=LatencyLog(); log.record('stt', 10); log.record('total', 20)
    log.reset('stt')
    assert log.samples('stt') == [] and log.samples('total') == [20.0]
    log.reset()
    assert log.stats() == {}

def test_runtime_answers_latency_stats_request():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav', latency_window=5, latency_p95_budget_ms=1000)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        runtime.latency.record('total', 120); runtime.latency.record('total', 300)
        await runtime.handle(ws, json.dumps({'type':'latency_stats'}))
        event=_events(ws)[-1]
        assert event['type'] == 'latency_stats' and event['budget_ms'] == 1000
        assert event['stats']['total']['count'] == 2 and event['stats']['total']['p95'] == 300.0
        assert event['regressed'] == []
        await runtime.handle(ws, json.dumps({'type':'latency_stats','reset':True}))
        assert _events(ws)[-1]['stats'] == {}
    asyncio.run(run())

def test_turn_records_latency_and_emits_stats():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav')
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        runtime.pcm_chunks[9] = [b'\xff\x7f' * 16]
        await runtime.handle(ws, json.dumps({'type':'finish_listening','request_id':9,'format':'pcm_s16le'}))
        await runtime.active_task
        events=_events(ws)
        metrics=next(event for event in events if event['type'] == 'pipeline_metrics')
        stats=next(event for event in events if event['type'] == 'latency_stats')
        assert stats['stats']['total']['count'] == 1
        assert stats['stats']['total']['p95'] == metrics['total_ms']
        assert set(stats['stats']) == {'stt','llm','tts','total'}
    asyncio.run(run())
