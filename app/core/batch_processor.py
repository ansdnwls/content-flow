"""Shared async batch writing helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class BatchWriter(Generic[T]):
    """Collect small writes and flush them in batches."""

    def __init__(
        self,
        write_batch: Callable[[list[T]], Awaitable[int]],
        *,
        flush_interval: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        self.write_batch = write_batch
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self._queue: list[T] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None

    async def enqueue(self, item: T) -> None:
        async with self._lock:
            self._queue.append(item)
            should_flush = len(self._queue) >= self.batch_size
            if not should_flush and self._flush_task is None:
                self._flush_task = asyncio.create_task(self._flush_later())

        if should_flush:
            await self.flush()

    async def enqueue_many(self, items: list[T]) -> None:
        async with self._lock:
            self._queue.extend(items)
            should_flush = len(self._queue) >= self.batch_size
            if not should_flush and self._flush_task is None:
                self._flush_task = asyncio.create_task(self._flush_later())

        if should_flush:
            await self.flush()

    async def _flush_later(self) -> None:
        try:
            await asyncio.sleep(self.flush_interval)
            await self.flush()
        except asyncio.CancelledError:
            return
        finally:
            async with self._lock:
                if self._flush_task is not None and self._flush_task.done():
                    self._flush_task = None

    async def flush(self) -> int:
        total = 0

        while True:
            async with self._lock:
                if not self._queue:
                    if self._flush_task is not None and self._flush_task.done():
                        self._flush_task = None
                    return total

                batch = self._queue[: self.batch_size]
                self._queue = self._queue[self.batch_size :]

                current_task = self._flush_task
                self._flush_task = None

            if current_task is not None and current_task is not asyncio.current_task():
                current_task.cancel()

            total += await self.write_batch(batch)

    async def close(self) -> int:
        async with self._lock:
            task = self._flush_task
            self._flush_task = None
        if task is not None:
            try:
                if not task.done() and not task.get_loop().is_closed():
                    task.cancel()
            except RuntimeError:
                pass
        return await self.flush()
