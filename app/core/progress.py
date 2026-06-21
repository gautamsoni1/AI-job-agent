"""
In-memory pipeline progress broadcaster — WebSocket pub/sub per run_id.
Single-process only. Agar multi-worker deployment karna pade future mein,
yahan ka dict-based store Redis pub/sub se replace karo — interface same rahega.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
import structlog

logger = structlog.get_logger()


class ProgressManager:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._history: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(run_id, []).append(queue)
            # Late-connecting WS client ko backlog replay kar do
            for event in self._history.get(run_id, []):
                queue.put_nowait(event)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        async with self._lock:
            subs = self._subscribers.get(run_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs:
                self._subscribers.pop(run_id, None)

    async def emit(
        self,
        run_id: str,
        stage: str,
        message: str,
        percent: Optional[int] = None,
        data: Optional[dict] = None,
    ):
        event = {
            "stage": stage,      # RESUME_PARSING | ATS_SCORING | JOB_DISCOVERY | DONE | ERROR ...
            "message": message,
            "percent": percent,  # 0-100
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        async with self._lock:
            self._history.setdefault(run_id, []).append(event)
            self._history[run_id] = self._history[run_id][-200:]  # cap growth
            subs = list(self._subscribers.get(run_id, []))
        for queue in subs:
            queue.put_nowait(event)
        logger.info("pipeline_progress", run_id=run_id, stage=stage, message=message, percent=percent)

    def cleanup(self, run_id: str):
        self._history.pop(run_id, None)
        self._subscribers.pop(run_id, None)


progress_manager = ProgressManager()