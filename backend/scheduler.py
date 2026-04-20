"""DiagnosticsScheduler — background asyncio task that periodically runs diagnostics."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Coroutine, Any

_logger = logging.getLogger(__name__)


class DiagnosticsScheduler:
    def __init__(self, run_fn: Callable[[], Coroutine[Any, Any, Any]], interval_seconds: int = 1800) -> None:
        self._run_fn = run_fn
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            _logger.info("DiagnosticsScheduler started (interval=%ds).", self._interval)

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            _logger.info("DiagnosticsScheduler stopped.")

    async def _loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval)
                try:
                    _logger.info("Running scheduled diagnostics.")
                    await self._run_fn()
                except Exception as exc:
                    _logger.error("Scheduled diagnostics run failed: %s", exc)
        except asyncio.CancelledError:
            pass
