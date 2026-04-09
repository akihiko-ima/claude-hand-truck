"""同期カメラ読み込みスレッド。

2台のカメラを1スレッドで同期して読み込み、ソフトウェアタイマーでFPSを固定する。
"""

import logging
import queue
import threading
import time
import traceback

import cv2
import numpy as np

from src.pipeline.data_classes import SyncFrameItem

logger = logging.getLogger(__name__)


class SyncCameraReadTask(threading.Thread):
    """2台のカメラを1スレッドで同期して読み込む。

    高精度タイマー（time.perf_counter）でソフトウェアFPS固定を行う。
    frame_queue が満杯の場合は最古フレームを破棄して最新フレームを挿入する（最新優先戦略）。
    """

    def __init__(
        self,
        camera_ids: list[int],
        frame_queue: queue.Queue,
        stop_event: threading.Event,
        target_fps: float = 30.0,
    ) -> None:
        super().__init__(name="SyncCameraReadTask", daemon=True)
        self._camera_ids = camera_ids
        self._frame_queue = frame_queue
        self._stop_event = stop_event
        self._target_fps = target_fps
        self._interval = 1.0 / target_fps
        self._frame_index = 0

    def run(self) -> None:
        caps: dict[int, cv2.VideoCapture] = {}

        try:
            for cam_id in self._camera_ids:
                cap = cv2.VideoCapture(cam_id)
                if not cap.isOpened():
                    logger.error(f"カメラ ID:{cam_id} を開けませんでした")
                    return
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1.0)
                cap.set(cv2.CAP_PROP_FPS, self._target_fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                caps[cam_id] = cap
                logger.info(f"カメラ ID:{cam_id} オープン成功")

            logger.info(
                f"SyncCameraReadTask 開始 (cameras={self._camera_ids}, fps={self._target_fps})"
            )

            next_time = time.perf_counter()

            while not self._stop_event.is_set():
                next_time += self._interval
                frames: dict[int, np.ndarray] = {}
                all_ok = True

                for cam_id, cap in caps.items():
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning(f"camera_id={cam_id} フレーム取得失敗、スキップ")
                        all_ok = False
                        break
                    frames[cam_id] = frame

                if all_ok:
                    item = SyncFrameItem(
                        frame_index=self._frame_index,
                        timestamp=int(time.time() * 1000),
                        frames=frames,
                    )
                    # キュー満杯時は最古を破棄して最新を挿入
                    try:
                        self._frame_queue.put_nowait(item)
                    except queue.Full:
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self._frame_queue.put_nowait(item)
                    self._frame_index += 1

                sleep_time = next_time - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # 処理落ち時はドリフトを防ぐためタイマーをリセット
                    next_time = time.perf_counter()

        except Exception:
            logger.error("SyncCameraReadTask で例外が発生しました")
            traceback.print_exc()
        finally:
            for cap in caps.values():
                cap.release()
            logger.info("SyncCameraReadTask 終了")
