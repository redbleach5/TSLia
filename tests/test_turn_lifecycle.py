import asyncio
from liya.server import LiyaRuntime

def test_new_turn_invalidates_previous_generation():
    async def run():
        runtime = LiyaRuntime(None)
        first = runtime.begin_turn(1)
        second = runtime.begin_turn(2)
        assert first != second
        assert not runtime.is_current(first)
        assert runtime.is_current(second)
        assert runtime.active_reply.endswith(str(second))
    asyncio.run(run())

def test_cancel_sets_event():
    async def run():
        runtime = LiyaRuntime(None)
        turn = runtime.begin_turn(3)
        runtime.cancel_active()
        assert runtime.cancel_event.is_set()
        assert not runtime.is_current(turn + 1)
    asyncio.run(run())
