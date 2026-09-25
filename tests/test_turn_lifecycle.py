import asyncio
from liya.server import LiyaRuntime
from liya.turn import TurnManager, Turn

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

def test_turn_manager_isolated():
    async def run():
        tm = TurnManager()
        turn_id = tm.begin_turn(42)
        assert tm.generation == 1
        assert tm.active_turn_id == 1
        assert tm.active_reply == "reply-42-1"
        assert tm.active_turn == Turn(turn_id=1, reply_id="reply-42-1", generation=1, cancel_event=tm.cancel_event)
        assert tm.is_current(1)
        assert not tm.is_current(2)
        assert not tm.is_current(None)

        async def dummy():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy())
        tm.llm_tasks.append(task)
        tm.cancel_active()
        assert tm.cancel_event.is_set()
        assert task.cancelling() or task.cancelled()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled()
    asyncio.run(run())
