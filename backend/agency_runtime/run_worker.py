from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable


LOGGER = logging.getLogger("agency_runtime.run_worker")


class DurableRunWorker:
    """Small in-process worker loop over a durable shared queue.

    Queue membership, leases, fencing tokens, and checkpoints are persisted by the
    supplied executor. The thread itself owns no business state and can be restarted.
    """

    def __init__(
        self,
        execute_one: Callable[[str], bool],
        *,
        poll_interval_seconds: float = 0.35,
        worker_id: str = "",
    ) -> None:
        if poll_interval_seconds < 0.05 or poll_interval_seconds > 60:
            raise ValueError("run worker poll interval must be between 0.05 and 60 seconds")
        self._execute_one = execute_one
        self._poll_interval_seconds = poll_interval_seconds
        self.worker_id = worker_id or "worker-{}".format(uuid.uuid4().hex)
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="agency-durable-run-worker",
            daemon=True,
        )

    @property
    def running(self) -> bool:
        return self._thread.is_alive() and not self._stop.is_set()

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()

    def stop(self, timeout_seconds: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout_seconds)
        if self._thread.is_alive():
            raise RuntimeError("durable run worker did not stop")

    def _run(self) -> None:
        while not self._stop.is_set():
            progressed = False
            try:
                progressed = self._execute_one(self.worker_id)
            except Exception:
                LOGGER.exception("durable_run_worker_iteration_failed worker_id=%s", self.worker_id)
            self._stop.wait(self._poll_interval_seconds)
