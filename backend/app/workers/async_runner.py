"""Run async coroutines from synchronous Celery tasks."""

import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[object, object, T]) -> T:
    """
    Execute a coroutine from a sync Celery task.

    Always uses asyncio.run() in the worker process so asyncpg engines are bound
    to a single fresh loop per task invocation.
    """
    from app.core.cache import reset_cache_client
    import app.db.session as session_module

    session_module.engine = None
    session_module.read_engine = None
    session_module.AsyncWriteSession = None
    session_module.AsyncReadSession = None
    reset_cache_client()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()
