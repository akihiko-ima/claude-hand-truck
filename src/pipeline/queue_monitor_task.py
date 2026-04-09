"""キューサイズ監視スレッド。

パイプライン内の各キューのサイズを定期的にログ出力する。
処理の詰まりや遅延の診断に使用する。
"""

import logging
import queue
import threading
import time

logger = logging.getLogger(__name__)


class QueueMonitorTask(threading.Thread):
    """1秒ごとに各キューのサイズをログ出力する監視スレッド。"""

    def __init__(
        self,
        queues: dict[str, queue.Queue],
        stop_event: threading.Event,
        interval: float = 1.0,
    ) -> None:
        super().__init__(name="QueueMonitorTask", daemon=True)
        self._queues = queues
        self._stop_event = stop_event
        self._interval = interval

    def run(self) -> None:
        logger.info("QueueMonitorTask 開始")
        while not self._stop_event.is_set():
            parts = "  ".join(f"{k}={q.qsize()}" for k, q in self._queues.items())
            logger.info(f"[QUEUE] {parts}")
            time.sleep(self._interval)
        logger.info("QueueMonitorTask 終了")
