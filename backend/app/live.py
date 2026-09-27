"""Live streaming: fans out Source.stream() updates to subscribed WebSocket clients."""

from __future__ import annotations

import asyncio
import logging

import pandas as pd
from fastapi import WebSocket

from app.archive.writer import ArchiveWriter
from app.sources import REGISTRY

logger = logging.getLogger(__name__)


class LiveManager:
    def __init__(self, writer: ArchiveWriter) -> None:
        self.writer = writer
        self._subscribers: dict[str, set[WebSocket]] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def subscribe(self, series_id: str, websocket: WebSocket) -> None:
        self._subscribers.setdefault(series_id, set()).add(websocket)
        if series_id not in self._tasks:
            self._tasks[series_id] = asyncio.create_task(self._run(series_id))

    async def unsubscribe(self, series_id: str, websocket: WebSocket) -> None:
        subscribers = self._subscribers.get(series_id)
        if not subscribers:
            return
        subscribers.discard(websocket)
        if not subscribers:
            del self._subscribers[series_id]
            task = self._tasks.pop(series_id, None)
            if task:
                task.cancel()

    async def _run(self, series_id: str) -> None:
        source_cls = REGISTRY.get(series_id.partition(":")[0])
        if source_cls is None:
            logger.warning("No source plugin for live series %s", series_id)
            return

        source = source_cls(series_id)
        try:
            async for point in source.stream():
                self.writer.write(pd.DataFrame([point]))
                await self._broadcast(series_id, point)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Live stream for %s stopped unexpectedly", series_id)

    async def _broadcast(self, series_id: str, point: dict) -> None:
        message = {"series_id": series_id, "timestamp": point["timestamp"].isoformat(), "value": point["value"]}
        for websocket in list(self._subscribers.get(series_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                self._subscribers.get(series_id, set()).discard(websocket)
