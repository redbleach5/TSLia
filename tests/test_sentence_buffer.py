from liya.server import SentenceBuffer

def test_sentence_buffer_splits_russian_sentences():
    buffer=SentenceBuffer()
    assert buffer.add('Привет, это первая фраза.') == 'Привет, это первая фраза.'
    assert buffer.add(' А вторая пока не готова.') == 'А вторая пока не готова.'
    assert buffer.flush() is None

def test_sentence_buffer_flushes_remainder():
    buffer=SentenceBuffer(); buffer.add('Короткий ответ без знака')
    assert buffer.flush() == 'Короткий ответ без знака'
