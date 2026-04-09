"""CSV書き出しスレッド。

DetectionResultItem を受け取り、手のキーポイント（21点）を CSV に記録する。
source_camera_id カラムにどちらのカメラで検出したかを記録する。
"""

import csv
import logging
import queue
import threading
import traceback
from pathlib import Path

from src.pipeline.data_classes import DetectionResultItem

logger = logging.getLogger(__name__)

NUM_LANDMARKS = 21

_LM_HEADER = [f"lm{i}_{a}" for i in range(NUM_LANDMARKS) for a in ("x", "y", "z")]
_HEADER = ["frame_index", "timestamp_ms", "detected", "source_camera_id"] + _LM_HEADER


class CsvWriterTask(threading.Thread):
    """手検出結果のキーポイント座標を CSV に書き出すスレッド。

    各行は1フレーム分のデータを表す。
    検出成功時は21キーポイントの (x, y, z) を列に展開して記録する。
    検出失敗時は landmark 列を空文字で埋める。

    座標値は MediaPipe の画像正規化座標（[0, 1]）。
    """

    def __init__(
        self,
        csv_queue: queue.Queue,
        stop_event: threading.Event,
        output_path: str = "logs/hand_landmarks.csv",
    ) -> None:
        super().__init__(name="CsvWriterTask", daemon=True)
        self._csv_queue = csv_queue
        self._stop_event = stop_event
        self._output_path = Path(output_path)

    def run(self) -> None:
        try:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"CsvWriterTask 開始 → {self._output_path}")

            with open(self._output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(_HEADER)

                while not self._stop_event.is_set():
                    try:
                        item: DetectionResultItem = self._csv_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    row: list[str | int | float] = [
                        item.frame_index,
                        item.timestamp,
                        int(item.detected),
                        item.source_camera_id if item.source_camera_id is not None else "",
                    ]

                    if item.detected and len(item.raw_landmarks) == NUM_LANDMARKS:
                        for x, y, z in item.raw_landmarks:
                            row.extend([f"{x:.6f}", f"{y:.6f}", f"{z:.6f}"])
                    else:
                        row.extend([""] * (NUM_LANDMARKS * 3))

                    writer.writerow(row)
                    f.flush()

        except Exception:
            logger.error("CsvWriterTask で例外が発生しました")
            traceback.print_exc()
        finally:
            logger.info("CsvWriterTask 終了")
