import logging
import time

import cv2
import mediapipe as mp
import numpy as np

from src.detection.calibration_manager import CalibrationManager
from src.models.calibration_config import CalibrationConfig
from src.models.hand_position import HandPosition

logger = logging.getLogger(__name__)


class HandDetector:
    """MediaPipeを使用した手座標検出クラス。

    フレームから手の位置を検出し、CalibrationManagerを使って
    テーブル正規化座標に変換する。
    MediaPipeの初期化はコンストラクタで1度だけ行う（フレームループ内での初期化は禁止）。
    """

    def __init__(self, calibration_manager: CalibrationManager) -> None:
        """MediaPipe Handsを初期化する。

        Args:
            calibration_manager: 座標変換に使用するキャリブレーションマネージャー
        """
        self._calib_manager = calibration_manager

        try:
            self._hands = mp.solutions.hands.Hands(  # type: ignore[attr-defined]
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception as e:
            logger.critical(f"手検出エンジンの初期化に失敗しました。({e})")
            raise RuntimeError("手検出エンジンの初期化に失敗しました。") from e

        self._mp_drawing = mp.solutions.drawing_utils  # type: ignore[attr-defined]
        self._mp_hands = mp.solutions.hands  # type: ignore[attr-defined]

    def detect(
        self,
        frame: np.ndarray,
        camera_id: int,
        calib: CalibrationConfig,
    ) -> list[HandPosition]:
        """フレームから手座標を検出し、テーブル正規化座標で返す。

        Args:
            frame: カメラフレーム（BGR形式）
            camera_id: フレームを取得したカメラID
            calib: 座標変換に使用するキャリブレーション設定

        Returns:
            検出された手のリスト（検出なしの場合は空リスト）
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb_frame)

        if not results.multi_hand_landmarks:
            return []

        positions: list[HandPosition] = []
        h, w = frame.shape[:2]
        timestamp = time.time()

        for hand_landmarks, hand_world in zip(
            results.multi_hand_landmarks,
            results.multi_handedness,
        ):
            # 手首（landmark 0）の座標をピクセル座標に変換
            wrist = hand_landmarks.landmark[0]
            px = int(wrist.x * w)
            py = int(wrist.y * h)

            # キャリブレーション変換でテーブル正規化座標に変換
            x_norm, y_norm = self._calib_manager.transform_point(calib, px, py)

            confidence = hand_world.classification[0].score

            positions.append(
                HandPosition(
                    x_normalized=x_norm,
                    y_normalized=y_norm,
                    timestamp=timestamp,
                    camera_id=camera_id,
                    confidence=confidence,
                )
            )

        return positions

    def draw_landmarks(
        self, frame: np.ndarray, positions: list[HandPosition]
    ) -> np.ndarray:
        """検出した手の位置をフレームに描画して返す。

        Args:
            frame: 描画対象のカメラフレーム
            positions: 描画する手座標リスト

        Returns:
            描画済みフレーム
        """
        result = frame.copy()
        rgb_frame = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        detection_results = self._hands.process(rgb_frame)

        if detection_results.multi_hand_landmarks:
            for hand_landmarks in detection_results.multi_hand_landmarks:
                self._mp_drawing.draw_landmarks(
                    result,
                    hand_landmarks,
                    self._mp_hands.HAND_CONNECTIONS,
                )

        return result

    def close(self) -> None:
        """MediaPipeリソースを解放する。"""
        self._hands.close()
