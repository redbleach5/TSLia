def test_default_selection_is_batch():
    from liya.stt import LocalHttpSTT, select_stt
    class C:
        capabilities = type('Caps', (), {'stt_stream': False})()
    assert type(select_stt(C())) is LocalHttpSTT


def test_streaming_selection_wraps_backend():
    from liya.stt import StreamingSTTBackend, select_stt
    class C:
        capabilities = type('Caps', (), {'stt_stream': True})()
    assert isinstance(select_stt(C()), StreamingSTTBackend)


def test_macos_backend_falls_back_without_bridge():
    from liya.stt import MacSpeechAnalyzerSTT, LocalHttpSTT
    class C:
        def transcribe(self, path): return 'batch'
        capabilities = type('Caps', (), {'stt_stream': False})()
    backend = MacSpeechAnalyzerSTT(fallback=LocalHttpSTT(C()))
    assert backend.transcribe('ignored') == 'batch'

