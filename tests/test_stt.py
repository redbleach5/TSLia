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
