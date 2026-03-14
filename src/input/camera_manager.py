import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_INTERVAL_SECONDS = 3.0


class CameraManager:
    """複数カメラの初期化・フレーム取得・再接続管理を担うクラス。

    OpenCVのカメラ操作を閉じ込め、上位レイヤーにはフレーム辞書として提供する。
    """

    def __init__(self, camera_ids: list[int]) -> None:
        """指定されたカメラIDのリストでカメラを初期化する。

        Args:
            camera_ids: 使用するカメラIDのリスト（例: [0, 1]）
        """
        self._camera_ids = camera_ids
        self._captures: dict[int, cv2.VideoCapture] = {}
        self._connect_all()

    def _connect_all(self) -> None:
        """全カメラへの接続を試みる。"""
        for camera_id in self._camera_ids:
            self._connect(camera_id)

    def _connect(self, camera_id: int) -> bool:
        """指定カメラへの接続を試みる。

        Args:
            camera_id: 接続するカメラID

        Returns:
            接続成功の場合 True
        """
        cap = cv2.VideoCapture(camera_id)
        if cap.isOpened():
            self._captures[camera_id] = cap
            logger.info(f"カメラ{camera_id}に接続しました。")
            return True
        else:
            cap.release()
            logger.warning(f"カメラ{camera_id}への接続に失敗しました。")
            return False

    def get_frames(self) -> dict[int, np.ndarray]:
        """接続済みカメラから全フレームを取得する。

        取得失敗のカメラは自動再接続を試みる。

        Returns:
            カメラIDをキー、フレーム(ndarray)を値とした辞書。
            取得失敗のカメラは辞書に含まれない。
        """
        frames: dict[int, np.ndarray] = {}
        for camera_id in self._camera_ids:
            cap = self._captures.get(camera_id)
            if cap is None or not cap.isOpened():
                self._attempt_reconnect(camera_id)
                cap = self._captures.get(camera_id)
                if cap is None:
                    continue

            ret, frame = cap.read()
            if ret:
                frames[camera_id] = frame
            else:
                logger.warning(f"カメラ{camera_id}のフレーム取得に失敗しました。再接続を試みます。")
                self._attempt_reconnect(camera_id)

        return frames

    def _attempt_reconnect(self, camera_id: int) -> None:
        """カメラへの再接続を最大 MAX_RECONNECT_ATTEMPTS 回試みる。"""
        if camera_id in self._captures:
            self._captures[camera_id].release()
            del self._captures[camera_id]

        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            print(f"カメラ{camera_id}に接続できません。再試行中... ({attempt}/{MAX_RECONNECT_ATTEMPTS})")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
            if self._connect(camera_id):
                return

        logger.error(f"カメラ{camera_id}への再接続に失敗しました（最大試行回数超過）。")

    def is_connected(self, camera_id: int) -> bool:
        """指定カメラが接続済みかどうかを返す。"""
        cap = self._captures.get(camera_id)
        return cap is not None and cap.isOpened()

    def release(self) -> None:
        """全カメラリソースを解放する。"""
        for cap in self._captures.values():
            cap.release()
        self._captures.clear()
        logger.info("全カメラリソースを解放しました。")
