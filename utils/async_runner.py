import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class AsyncRunner:
    """Manages a single, long-lived background asyncio event loop thread for synchronous execution contexts (e.g., Streamlit UI)."""

    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def _ensure_loop_running(cls) -> asyncio.AbstractEventLoop:
        with cls._lock:
            if cls._loop is None or cls._loop.is_closed():
                cls._loop = asyncio.new_event_loop()
                cls._thread = threading.Thread(
                    target=cls._run_event_loop,
                    args=(cls._loop,),
                    daemon=True,
                    name="AsyncRunnerLoopThread",
                )
                cls._thread.start()
            return cls._loop

    @staticmethod
    def _run_event_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    @classmethod
    def run(cls, coro: Coroutine[Any, Any, T]) -> T:
        """Executes an async coroutine on the long-lived background event loop synchronously."""
        loop = cls._ensure_loop_running()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Convenience helper to run coroutines on the long-lived background event loop."""
    return AsyncRunner.run(coro)
