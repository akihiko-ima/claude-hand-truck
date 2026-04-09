"""ZeroMQ PUSH 送信スレッド。

DetectionResultItem を受け取り、検出した右手のグリッド座標を
ZeroMQ PUSH ソケット経由で送信する。

送信フォーマット（JSON）:
    {"timestamp": 1234567890.123, "row": 1, "col": 3, "valid": true}

フィールド:
    timestamp  フレーム取得時の Unix タイムスタンプ（秒、float）
    row        手が位置するグリッド行インデックス（0始まり）。valid=false 時は null
    col        手が位置するグリッド列インデックス（0始まり）。valid=false 時は null
    valid      カメラで右手を検出できたかのフラグ

受信側は tcp://localhost:5555 に ZeroMQ PULL ソケットを接続する。
"""

import json
import logging
import queue
import threading
import traceback

import zmq

from src.pipeline.data_classes import DetectionResultItem

logger = logging.getLogger(__name__)


class ZmqSenderTask(threading.Thread):
    """手のグリッド座標を ZeroMQ PUSH で送信するスレッド。

    grid_rows / grid_cols を使って HandPosition の正規化座標を
    グリッドインデックスに変換する。変換ロジックは GridTracker と同一。
    """

    def __init__(
        self,
        zmq_queue: queue.Queue,
        stop_event: threading.Event,
        endpoint: str,
        grid_rows: int,
        grid_cols: int,
    ) -> None:
        """
        Args:
            zmq_queue: DetectionResultItem を受け取るキュー
            stop_event: パイプライン共通の停止フラグ
            endpoint:   ZeroMQ PUSH ソケットのバインドアドレス（例: "tcp://*:5555"）
            grid_rows:  グリッドの行数（config.grid.rows）
            grid_cols:  グリッドの列数（config.grid.cols）
        """
        super().__init__(name="ZmqSenderTask", daemon=True)
        self._zmq_queue = zmq_queue
        self._stop_event = stop_event
        self._endpoint = endpoint
        self._grid_rows = grid_rows
        self._grid_cols = grid_cols

    def _to_grid(self, x_norm: float, y_norm: float) -> tuple[int, int]:
        """テーブル正規化座標をグリッドの (row, col) に変換する。

        GridTracker._position_to_cell() と同一ロジック。
        """
        col = max(0, min(int(x_norm * self._grid_cols), self._grid_cols - 1))
        row = max(0, min(int(y_norm * self._grid_rows), self._grid_rows - 1))
        return row, col

    def run(self) -> None:
        context = zmq.Context()
        socket = context.socket(zmq.PUSH)

        try:
            socket.bind(self._endpoint)
            logger.info(f"ZmqSenderTask 開始 → {self._endpoint}")

            while not self._stop_event.is_set():
                try:
                    item: DetectionResultItem = self._zmq_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # グリッド座標の計算
                if item.detected and item.hand_positions:
                    pos = item.hand_positions[0]
                    row, col = self._to_grid(pos.x_normalized, pos.y_normalized)
                    payload = {
                        "timestamp": item.timestamp, 
                        "row": row,
                        "col": col,
                        "valid": True,
                    }
                else:
                    payload = {
                        "timestamp": item.timestamp,
                        "row": None,
                        "col": None,
                        "valid": False,
                    }

                socket.send_string(json.dumps(payload))

        except Exception:
            logger.error("ZmqSenderTask で例外が発生しました")
            traceback.print_exc()
        finally:
            socket.close()
            context.term()
            logger.info("ZmqSenderTask 終了")
