"""Async helpers used for blocking SDK and local-process calls."""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Callable
from typing import Any, cast


async def run_blocking[T](function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking function in a daemon thread without a global executor."""

    result_queue: queue.SimpleQueue[tuple[bool, object]] = queue.SimpleQueue()

    def worker() -> None:
        try:
            result = function(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - propagate the worker's original error
            result_queue.put((False, exc))
        else:
            result_queue.put((True, result))

    threading.Thread(target=worker, name="g1agent-blocking", daemon=True).start()
    while result_queue.empty():
        await asyncio.sleep(0.01)
    ok, result = result_queue.get()
    if not ok:
        raise cast(Exception, result)
    return cast(T, result)
