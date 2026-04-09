"""
ZeroMQ PULL 受信スレッド。

ZmqSenderTask から送信される JSON を受信し、
Python の dict に変換してキューに流す。

受信フォーマット（JSON）:
    {"timestamp": 1234567890.123, "row": 1, "col": 3, "valid": true}
"""

import json
import logging
import threading
import traceback
import queue
import zmq

logger = logging.getLogger(__name__)


class ZmqReceiverTask(threading.Thread):
    """ZeroMQ PULL でデータを受信するスレッド"""

    def __init__(
        self,
        output_queue: queue.Queue,
        stop_event: threading.Event,
        endpoint: str = "tcp://localhost:5555",
    ) -> None:
        """
        Args:
            output_queue: 受信したデータ(dict)を流すキュー
            stop_event: 停止フラグ
            endpoint:   接続先（送信側のbindと一致させる）
        """
        super().__init__(name="ZmqReceiverTask", daemon=True)
        self._output_queue = output_queue
        self._stop_event = stop_event
        self._endpoint = endpoint

    def run(self) -> None:
        context = zmq.Context()
        socket = context.socket(zmq.PULL)

        try:
            socket.connect(self._endpoint)
            logger.info(f"ZmqReceiverTask 開始 → {self._endpoint}")

            while not self._stop_event.is_set():
                try:
                    msg = socket.recv_string(flags=zmq.NOBLOCK)
                except zmq.Again:
                    continue

                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    logger.warning(f"JSON decode失敗: {msg}")
                    continue

                # 必要ならバリデーション
                parsed = {
                    "timestamp": data.get("timestamp"),
                    "row": data.get("row"),
                    "col": data.get("col"),
                    "valid": data.get("valid"),
                }

                self._output_queue.put(parsed)

        except Exception:
            logger.error("ZmqReceiverTask で例外が発生しました")
            traceback.print_exc()
        finally:
            socket.close()
            context.term()
            logger.info("ZmqReceiverTask 終了")


if __name__ == "__main__":
    q = queue.Queue()
    stop_event = threading.Event()

    receiver = ZmqReceiverTask(
        output_queue=q,
        stop_event=stop_event,
        endpoint="tcp://localhost:5555",
    )
    receiver.start()

    try:
        while True:
            try:
                data = q.get(timeout=1)
                print(data)
            except queue.Empty:
                continue

    except KeyboardInterrupt:
        stop_event.set()
        receiver.join()
