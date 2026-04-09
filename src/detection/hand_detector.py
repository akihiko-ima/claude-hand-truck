import logging
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from src.app_config import HandDetectionConfig
from src.detection.calibration_manager import CalibrationManager
from src.models.calibration_config import CalibrationConfig
from src.models.hand_position import HandPosition

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "hand_landmarker.task"

_HAND_CONNECTIONS = [
    (c.start, c.end)
    for c in mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS
]


class HandDetector:
    """MediaPipe Tasks APIを使用した手座標検出クラス。

    フレームから手の位置を検出し、CalibrationManagerを使って
    テーブル正規化座標に変換する。
    MediaPipeの初期化はコンストラクタで1度だけ行う（フレームループ内での初期化は禁止）。
    """

    def __init__(
        self,
        calibration_manager: CalibrationManager,
        model_path: Path | None = None,
        hand_config: HandDetectionConfig | None = None,
    ) -> None:
        """MediaPipe HandLandmarkerを初期化する。

        Args:
            calibration_manager: 座標変換に使用するキャリブレーションマネージャー
            model_path: hand_landmarker.task モデルファイルのパス（省略時はデフォルト）
            hand_config: 手検出設定（省略時はデフォルト値）
        """
        self._calib_manager = calibration_manager
        self._config = hand_config or HandDetectionConfig()
        self._last_timestamp_ms: int = -1
        self._last_filtered_landmarks: list = []

        path = model_path or _MODEL_PATH

        try:
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=self._config.num_hands,
                min_hand_detection_confidence=self._config.min_detection_confidence,
                min_hand_presence_confidence=self._config.min_presence_confidence,
                min_tracking_confidence=self._config.min_tracking_confidence,
            )
            self._detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        except Exception as e:
            logger.critical(f"手検出エンジンの初期化に失敗しました。({e})")
            raise RuntimeError("手検出エンジンの初期化に失敗しました。") from e

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
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int(time.time() * 1000)
        # VIDEO モードではタイムスタンプが単調増加である必要がある
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        results = self._detector.detect_for_video(mp_image, timestamp_ms)

        if not results.hand_landmarks:
            self._last_filtered_landmarks = []
            return []

        positions: list[HandPosition] = []
        filtered_landmarks: list = []
        h, w = frame.shape[:2]
        timestamp = time.time()

        for hand_landmarks, handedness in zip(results.hand_landmarks, results.handedness):
            # right_hand_only が有効な場合、右手（"Right"）以外をスキップ
            if self._config.right_hand_only and handedness[0].category_name != "Right":
                continue

            filtered_landmarks.append(hand_landmarks)

            # 手首（landmark 0）の座標をピクセル座標に変換
            wrist = hand_landmarks[0]
            px = int(wrist.x * w)
            py = int(wrist.y * h)

            # キャリブレーション変換でテーブル正規化座標に変換
            x_norm, y_norm = self._calib_manager.transform_point(calib, px, py)

            confidence = handedness[0].score

            positions.append(
                HandPosition(
                    x_normalized=x_norm,
                    y_normalized=y_norm,
                    timestamp=timestamp,
                    camera_id=camera_id,
                    confidence=confidence,
                )
            )

        self._last_filtered_landmarks = filtered_landmarks
        return positions

    def draw_landmarks(
        self, frame: np.ndarray, positions: list[HandPosition]
    ) -> np.ndarray:
        """最後の検出結果のランドマークをフレームに描画して返す。

        Args:
            frame: 描画対象のカメラフレーム
            positions: 検出済み手座標リスト（未使用、互換性維持のため保持）

        Returns:
            描画済みフレーム
        """
        result = frame.copy()
        if not self._last_filtered_landmarks:
            return result

        h, w = frame.shape[:2]
        for hand_landmarks in self._last_filtered_landmarks:
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]
            for start, end in _HAND_CONNECTIONS:
                cv2.line(result, pts[start], pts[end], (0, 255, 0), 2)
            for pt in pts:
                cv2.circle(result, pt, 4, (255, 0, 0), -1)

        return result

    def close(self) -> None:
        """MediaPipeリソースを解放する。"""
        self._detector.close()
