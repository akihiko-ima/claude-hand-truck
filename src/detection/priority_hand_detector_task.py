"""優先度付き手検出スレッド。

優先カメラで右手を検出し、失敗時はセカンダリカメラにフォールバックする。
MediaPipe IMAGE モードを使用し、カメラ別インスタンスで ThreadPoolExecutor 並列推論を行う。
"""

import concurrent.futures
import logging
import queue
import threading
import time
import traceback
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from src.app_config import HandDetectionConfig
from src.detection.calibration_manager import CalibrationManager
from src.models.calibration_config import CalibrationConfig
from src.models.hand_position import HandPosition
from src.pipeline.data_classes import DetectionResultItem, SyncFrameItem

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "hand_landmarker.task"

_HAND_CONNECTIONS = [
    (c.start, c.end)
    for c in mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS
]


class PriorityHandDetectTask(threading.Thread):
    """優先度付きマルチカメラ手検出スレッド。

    内部で ThreadPoolExecutor を使い priority/secondary カメラを並列推論する。
    detector はスレッドセーフでないため、カメラごとに独立したインスタンスを生成する。

    優先度ロジック:
        1. priority_camera_id のフレームで右手を検出
        2. 検出成功 → その結果を採用（secondary の結果は破棄）
        3. 検出失敗 → secondary カメラの結果を採用
        4. 両方失敗 → 空の HandPosition リストを出力
    """

    def __init__(
        self,
        camera_ids: list[int],
        priority_camera_id: int,
        frame_queue: queue.Queue,
        result_queue: queue.Queue,
        stop_event: threading.Event,
        calibration_manager: CalibrationManager,
        calibrations: dict[int, CalibrationConfig],
        hand_config: HandDetectionConfig | None = None,
        model_path: Path | None = None,
        debug_mode: bool = False,
        csv_queue: queue.Queue | None = None,
        zmq_queue: queue.Queue | None = None,
    ) -> None:
        super().__init__(name="PriorityHandDetectTask", daemon=True)

        if priority_camera_id not in camera_ids:
            raise ValueError(
                f"priority_camera_id={priority_camera_id} は camera_ids={camera_ids} に含まれていません"
            )
        if len(camera_ids) < 2:
            raise ValueError(
                f"camera_ids には2台以上のカメラが必要です（指定値: {camera_ids}）"
            )

        self._camera_ids = camera_ids
        self._priority_camera_id = priority_camera_id
        self._secondary_camera_id = next(c for c in camera_ids if c != priority_camera_id)
        self._frame_queue = frame_queue
        self._result_queue = result_queue
        self._stop_event = stop_event
        self._calib_manager = calibration_manager
        self._calibrations = calibrations
        self._hand_config = hand_config or HandDetectionConfig()
        self._model_path = str(model_path or _MODEL_PATH)
        self._debug_mode = debug_mode
        self._csv_queue = csv_queue
        self._zmq_queue = zmq_queue

    def _create_detector(self) -> mp_vision.HandLandmarker:
        """IMAGE モードの HandLandmarker インスタンスを生成する。"""
        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=self._model_path),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=self._hand_config.num_hands,
            min_hand_detection_confidence=self._hand_config.min_detection_confidence,
            min_hand_presence_confidence=self._hand_config.min_presence_confidence,
            min_tracking_confidence=self._hand_config.min_tracking_confidence,
        )
        return mp_vision.HandLandmarker.create_from_options(options)

    def _detect_right_hand(
        self,
        detector: mp_vision.HandLandmarker,
        frame: np.ndarray,
        camera_id: int,
    ) -> tuple[list[HandPosition], list[tuple[float, float, float]], mp_vision.HandLandmarkerResult | None]:
        """1台のカメラフレームから右手を検出する。

        right_hand_only が True の場合は "Right" ラベルのみを採用する。

        Returns:
            (hand_positions, raw_landmarks, mp_result) のタプル。
            hand_positions: テーブル正規化座標の HandPosition リスト
            raw_landmarks: 採用した最初の右手の21キーポイント（画像正規化座標 x, y, z）
            mp_result: MediaPipe の生検出結果（デバッグ描画に使用）
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(mp_image)

        if not result.hand_landmarks:
            return [], [], result

        positions: list[HandPosition] = []
        first_raw_landmarks: list[tuple[float, float, float]] = []
        h, w = frame.shape[:2]
        timestamp = time.time()
        calib = self._calibrations.get(camera_id)

        for hand_landmarks, handedness in zip(result.hand_landmarks, result.handedness):
            if self._hand_config.right_hand_only and handedness[0].category_name != "Right":
                continue

            # 最初の採用手のみ生ランドマークを記録
            if not first_raw_landmarks:
                first_raw_landmarks = [(lm.x, lm.y, lm.z) for lm in hand_landmarks]

            ref_point = hand_landmarks[9]  # 中指MCP関節（中指付け根）
            px = int(ref_point.x * w)
            py = int(ref_point.y * h)

            if calib is not None:
                x_norm, y_norm = self._calib_manager.transform_point(calib, px, py)
                # ROI（テーブル領域）外の手は積算対象外とする
                if not (0.0 <= x_norm <= 1.0 and 0.0 <= y_norm <= 1.0):
                    continue
            else:
                x_norm, y_norm = ref_point.x, ref_point.y

            positions.append(HandPosition(
                x_normalized=x_norm,
                y_normalized=y_norm,
                timestamp=timestamp,
                camera_id=camera_id,
                confidence=handedness[0].score,
            ))

        return positions, first_raw_landmarks, result

    def _annotate_frame(
        self,
        frame: np.ndarray,
        mp_result: mp_vision.HandLandmarkerResult,
        camera_id: int,
    ) -> np.ndarray:
        """フレームに手ランドマークとキャリブレーションエリアを描画して返す。

        旧 main.py の描画ロジックを再現する:
        - 採用色のランドマーク骨格（緑）と関節点（青）
        - キャリブレーションエリアの半透明オレンジオーバーレイ
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # 手ランドマークの描画
        for hand_landmarks, handedness in zip(mp_result.hand_landmarks, mp_result.handedness):
            if self._hand_config.right_hand_only and handedness[0].category_name != "Right":
                continue
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]
            for start, end in _HAND_CONNECTIONS:
                cv2.line(annotated, pts[start], pts[end], (0, 255, 0), 2)
            for pt in pts:
                cv2.circle(annotated, pt, 4, (255, 0, 0), -1)

        # キャリブレーションエリアの半透明オレンジオーバーレイ
        calib = self._calibrations.get(camera_id)
        if calib is not None:
            pts_arr = np.array(calib.table_corners, dtype=np.int32)
            overlay = annotated.copy()
            cv2.fillPoly(overlay, [pts_arr], (0, 200, 255))
            annotated = cv2.addWeighted(overlay, 0.12, annotated, 0.88, 0)
            cv2.polylines(annotated, [pts_arr], True, (0, 200, 255), 2)
            cv2.putText(
                annotated,
                f"Cam{camera_id} table area",
                (pts_arr[0][0], pts_arr[0][1] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1,
            )

        return annotated

    def run(self) -> None:
        detectors: dict[int, mp_vision.HandLandmarker] = {}

        try:
            if not Path(self._model_path).exists():
                logger.error(f"モデルファイルが見つかりません: {self._model_path}")
                return

            for cam_id in self._camera_ids:
                detectors[cam_id] = self._create_detector()

            logger.info(
                f"PriorityHandDetectTask 開始 "
                f"(priority=CAM{self._priority_camera_id}, secondary=CAM{self._secondary_camera_id})"
            )

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(self._camera_ids)
            ) as executor:
                while not self._stop_event.is_set():
                    try:
                        item: SyncFrameItem = self._frame_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    pri_frame = item.frames.get(self._priority_camera_id)
                    sec_frame = item.frames.get(self._secondary_camera_id)

                    # 両カメラを並列推論
                    future_pri = executor.submit(
                        self._detect_right_hand,
                        detectors[self._priority_camera_id],
                        pri_frame,
                        self._priority_camera_id,
                    ) if pri_frame is not None else None

                    future_sec = executor.submit(
                        self._detect_right_hand,
                        detectors[self._secondary_camera_id],
                        sec_frame,
                        self._secondary_camera_id,
                    ) if sec_frame is not None else None

                    pri_positions, pri_raw, pri_mp = (
                        future_pri.result() if future_pri else ([], [], None)
                    )
                    sec_positions, sec_raw, sec_mp = (
                        future_sec.result() if future_sec else ([], [], None)
                    )

                    # 優先度ロジック
                    if pri_positions:
                        hand_positions = pri_positions
                        raw_landmarks = pri_raw
                        source_camera_id = self._priority_camera_id
                    elif sec_positions:
                        hand_positions = sec_positions
                        raw_landmarks = sec_raw
                        source_camera_id = self._secondary_camera_id
                    else:
                        hand_positions = []
                        raw_landmarks = []
                        source_camera_id = None

                    # デバッグモード: ランドマーク + キャリブエリアをフレームに描画
                    debug_frames: dict[int, np.ndarray] | None = None
                    if self._debug_mode:
                        debug_frames = {}
                        if pri_frame is not None and pri_mp is not None:
                            debug_frames[self._priority_camera_id] = self._annotate_frame(
                                pri_frame, pri_mp, self._priority_camera_id
                            )
                        if sec_frame is not None and sec_mp is not None:
                            debug_frames[self._secondary_camera_id] = self._annotate_frame(
                                sec_frame, sec_mp, self._secondary_camera_id
                            )

                    result_item = DetectionResultItem(
                        frame_index=item.frame_index,
                        timestamp=item.timestamp,
                        source_camera_id=source_camera_id,
                        hand_positions=hand_positions,
                        detected=bool(hand_positions),
                        raw_landmarks=raw_landmarks,
                        frames=debug_frames,
                    )
                    self._result_queue.put(result_item)
                    if self._csv_queue is not None:
                        self._csv_queue.put(result_item)
                    if self._zmq_queue is not None:
                        self._zmq_queue.put(result_item)

        except Exception:
            logger.error("PriorityHandDetectTask で例外が発生しました")
            traceback.print_exc()
        finally:
            for det in detectors.values():
                try:
                    det.close()
                except Exception:
                    logger.warning("HandLandmarker の close() 中に例外が発生しました")
            logger.info("PriorityHandDetectTask 終了")
