"""トラッキング・保存スレッド。

DetectionResultItem を受け取り、GridTracker でグリッドを更新し、
HeatmapRenderer でヒートマップを生成して DataStorage に保存する。
デバッグモード時は 1 秒ごとに DebugImageSaver で統合画像を保存する。
"""

import logging
import queue
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from src.models.cleaning_session import CleaningSession
from src.output.display_controller import DebugImageSaver
from src.output.heatmap_renderer import HeatmapRenderer
from src.pipeline.data_classes import DetectionResultItem
from src.storage.data_storage import DataStorage
from src.tracking.grid_tracker import GridTracker

logger = logging.getLogger(__name__)

_OUTPUTS_DIR = Path("outputs")


class TrackingAndStorageTask(threading.Thread):
    """グリッドトラッキング・ヒートマップ生成・セッション保存を担うスレッド。

    result_queue から DetectionResultItem を受け取り、GridTracker で清掃状態を更新し、
    都度 DataStorage にセッションデータを保存する。

    delta_time は FPS固定値（1.0 / target_fps）を定数として使用する。
    debug_mode が True の場合、1秒ごとに outputs/debug.jpg を更新する。
    """

    def __init__(
        self,
        result_queue: queue.Queue,
        stop_event: threading.Event,
        tracker: GridTracker,
        storage: DataStorage,
        renderer: HeatmapRenderer,
        session: CleaningSession,
        target_fps: float = 30.0,
        debug_mode: bool = False,
        total_cells: int = 21,
    ) -> None:
        super().__init__(name="TrackingAndStorageTask", daemon=True)
        self._result_queue = result_queue
        self._stop_event = stop_event
        self._tracker = tracker
        self._storage = storage
        self._renderer = renderer
        self._session = session
        self._delta_time = 1.0 / target_fps
        self._debug_mode = debug_mode
        self._debug_saver: DebugImageSaver | None = None
        if debug_mode:
            _OUTPUTS_DIR.mkdir(exist_ok=True)
            self._debug_saver = DebugImageSaver(_OUTPUTS_DIR, total_cells=total_cells)
            logger.info(f"デバッグモード: 画像を {_OUTPUTS_DIR}/debug.jpg に1秒ごとに保存します")

    def run(self) -> None:
        logger.info("TrackingAndStorageTask 開始")
        last_debug_save = 0.0
        try:
            while not self._stop_event.is_set():
                try:
                    item: DetectionResultItem = self._result_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                self._tracker.update(item.hand_positions, self._delta_time)
                grid = self._tracker.get_grid()
                cleaning_rate = self._tracker.get_cleaning_rate()

                self._session.grid_cells = grid
                self._session.cleaning_rate = cleaning_rate

                heatmap = self._renderer.render(grid)
                self._storage.save_session(self._session, heatmap)

                # デバッグ画像を1秒ごとに保存
                if (
                    self._debug_saver is not None
                    and item.frames is not None
                    and time.time() - last_debug_save >= 1.0
                ):
                    self._debug_saver.save(item.frames, heatmap, cleaning_rate)
                    last_debug_save = time.time()

        except Exception:
            logger.error("TrackingAndStorageTask で例外が発生しました")
            traceback.print_exc()
        finally:
            # 停止後に最終セッションデータを保存
            try:
                self._session.ended_at = datetime.now().isoformat()
                self._session.cleaning_rate = self._tracker.get_cleaning_rate()
                heatmap = self._renderer.render(self._tracker.get_grid())
                self._storage.save_session(self._session, heatmap)
            except Exception:
                logger.error("TrackingAndStorageTask の終了処理中に例外が発生しました")
                traceback.print_exc()
            logger.info("TrackingAndStorageTask 終了")

    @property
    def session(self) -> CleaningSession:
        """現在のセッションデータを返す（終了後の参照用）。"""
        return self._session
