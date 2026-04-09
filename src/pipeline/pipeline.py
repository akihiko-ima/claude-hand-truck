"""手検出パイプラインのオーケストレーター。

Producer-Consumer パターンで4〜5本のスレッドを管理し、
カメラ読み込みから手検出・グリッドトラッキング・データ保存までの
一連の処理を並列化する。

スレッド間のデータ受け渡しにはすべて queue.Queue を使用する。
各スレッドは daemon=True のため、メインスレッド終了時に自動回収される。
stop_event を共有し、Ctrl+C でパイプライン全体を協調停止させる。

データフロー:
    SyncCameraReadTask
        ↓ frame_queue (SyncFrameItem)
    PriorityHandDetectTask
        ↓ result_queue (DetectionResultItem)   ↓ csv_queue (同じアイテム)
    TrackingAndStorageTask                     CsvWriterTask
"""

import logging
import queue
import time
import threading

from src.app_config import AppConfig
from src.detection.calibration_manager import CalibrationManager
from src.detection.priority_hand_detector_task import PriorityHandDetectTask
from src.input.sync_camera_reader import SyncCameraReadTask
from src.models.calibration_config import CalibrationConfig
from src.output.heatmap_renderer import HeatmapRenderer
from src.pipeline.csv_writer_task import CsvWriterTask
from src.pipeline.queue_monitor_task import QueueMonitorTask
from src.pipeline.tracking_task import TrackingAndStorageTask
from src.storage.data_storage import DataStorage
from src.tracking.grid_tracker import GridTracker

logger = logging.getLogger(__name__)


class HandDetectionPipeline:
    """手検出パイプラインのオーケストレーター。

    通常モードのスレッド構成（3〜4本）:
        SyncCameraReadTask      × 1  FPS固定で2台のカメラを同期読み込み
        PriorityHandDetectTask  × 1  優先カメラ→セカンダリのフォールバック検出
        TrackingAndStorageTask  × 1  グリッド更新・ヒートマップ生成・セッション保存
        CsvWriterTask           × 1  手のキーポイントをCSVに記録（csv.enabled 時のみ）

    デバッグモード追加スレッド（debug 引数指定時のみ）:
        QueueMonitorTask        × 1  各キューのサイズを1秒ごとにログ出力

    キュー構成:
        frame_queue  SyncCameraReadTask → PriorityHandDetectTask
                     maxsize=config.pipeline.frame_queue_maxsize
                     満杯時は最古フレームを破棄して最新を優先（リアルタイム優先戦略）
        result_queue PriorityHandDetectTask → TrackingAndStorageTask
                     maxsize=0（無制限）
        csv_queue    PriorityHandDetectTask → CsvWriterTask（ファンアウト）
                     maxsize=0（無制限）、csv.enabled=false の場合は生成しない
    """

    def __init__(
        self,
        config: AppConfig,
        calib_manager: CalibrationManager,
        calibrations: dict[int, CalibrationConfig],
        table_id: str = "table_01",
        debug_mode: bool = False,
    ) -> None:
        """パイプラインを初期化する。スレッドはまだ起動しない。

        Args:
            config: アプリケーション設定（grid / hand_detection / pipeline / csv）
            calib_manager: ホモグラフィ変換に使用するキャリブレーションマネージャー
            calibrations: {camera_id: CalibrationConfig} の辞書
            table_id: 清掃セッションに紐づくテーブル識別子
            debug_mode: True のとき QueueMonitorTask を追加起動し
                        デバッグ画像を outputs/debug.jpg に保存する
        """
        self._config = config
        self._calib_manager = calib_manager
        self._calibrations = calibrations
        self._table_id = table_id
        self._debug_mode = debug_mode
        self._stop_event = threading.Event()   # 全スレッドが監視する停止フラグ
        self._threads: list[threading.Thread] = []
        self._tracking_task: TrackingAndStorageTask | None = None

    def start(self) -> None:
        """キュー・コンポーネントを初期化し、全スレッドを起動する。

        start() は一度だけ呼び出すこと。
        二度呼び出した場合の動作は未定義。
        """
        pl = self._config.pipeline
        grid_cfg = self._config.grid

        # ---- キューの生成 ------------------------------------------------
        # frame_queue: カメラフレームのバッファ。maxsize で上限を設けて
        #              消費が追いつかない場合に古いフレームを破棄する。
        frame_queue: queue.Queue = queue.Queue(maxsize=pl.frame_queue_maxsize)

        # result_queue: 検出結果をトラッキングタスクへ渡す。
        #               TrackingAndStorageTask は比較的高速なため無制限で問題ない。
        result_queue: queue.Queue = queue.Queue(maxsize=0)

        # csv_queue: result_queue からのファンアウト。
        #            config.csv.enabled=false の場合は生成しない（None のまま）。
        csv_queue: queue.Queue | None = (
            queue.Queue(maxsize=0) if self._config.csv.enabled else None
        )

        # ---- ビジネスロジックコンポーネントの初期化 -------------------------
        storage = DataStorage()
        session = storage.create_session(
            self._table_id,
            rows=grid_cfg.rows,
            cols=grid_cfg.cols,
        )

        tracker = GridTracker(
            rows=grid_cfg.rows,
            cols=grid_cfg.cols,
            clean_threshold_seconds=grid_cfg.clean_threshold_seconds,
        )
        tracker.reset()  # 新セッション開始時にグリッドを初期化

        renderer = HeatmapRenderer()

        # ---- スレッドの生成 -----------------------------------------------
        # TrackingAndStorageTask は session への参照を保持するため先に生成する
        total_cells = grid_cfg.rows * grid_cfg.cols
        self._tracking_task = TrackingAndStorageTask(
            result_queue=result_queue,
            stop_event=self._stop_event,
            tracker=tracker,
            storage=storage,
            renderer=renderer,
            session=session,
            target_fps=pl.target_fps,
            debug_mode=self._debug_mode,
            total_cells=total_cells,
        )

        # デバッグモード時のキュー監視対象（QueueMonitorTask に渡す辞書）
        monitor_queues: dict[str, queue.Queue] = {
            "FrameQ": frame_queue,
            "ResultQ": result_queue,
        }
        if csv_queue is not None:
            monitor_queues["CsvQ"] = csv_queue

        # 常時起動するスレッド（通常モード・デバッグモード共通）
        self._threads = [
            SyncCameraReadTask(
                camera_ids=pl.camera_ids,
                frame_queue=frame_queue,
                stop_event=self._stop_event,
                target_fps=pl.target_fps,
            ),
            PriorityHandDetectTask(
                camera_ids=pl.camera_ids,
                priority_camera_id=pl.priority_camera_id,
                frame_queue=frame_queue,
                result_queue=result_queue,
                stop_event=self._stop_event,
                calibration_manager=self._calib_manager,
                calibrations=self._calibrations,
                hand_config=self._config.hand_detection,
                debug_mode=self._debug_mode,
                csv_queue=csv_queue,        # None の場合はファンアウトしない
            ),
            self._tracking_task,
        ]

        # デバッグモード時のみ起動するスレッド
        if self._debug_mode:
            self._threads.append(QueueMonitorTask(
                queues=monitor_queues,
                stop_event=self._stop_event,
            ))

        # CSV 書き出しスレッド（config.csv.enabled=true の場合のみ起動）
        if csv_queue is not None:
            self._threads.append(CsvWriterTask(
                csv_queue=csv_queue,
                stop_event=self._stop_event,
                output_path=self._config.csv.output_path,
            ))

        for t in self._threads:
            t.start()

        logger.info(
            f"パイプライン起動完了 "
            f"(cameras={pl.camera_ids}, priority=CAM{pl.priority_camera_id}, "
            f"fps={pl.target_fps})"
        )

    def stop(self) -> None:
        """全スレッドに停止シグナルを送り、終了を待機する。

        stop_event をセットして各スレッドのループを抜けさせ、
        join() で最大 5 秒待機する。タイムアウトしたスレッドは
        daemon=True のためプロセス終了時に OS に回収される。
        """
        logger.info("パイプライン停止中...")
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=5.0)
            if t.is_alive():
                logger.warning(f"スレッド {t.name} が5秒以内に終了しませんでした")
        logger.info("パイプライン停止完了")

    def wait(self) -> None:
        """Ctrl+C まで待機するブロッキングメソッド。

        KeyboardInterrupt を捕捉して stop() を呼び出す。
        全スレッドが先に終了した場合も待機ループを抜ける。
        """
        logger.info("実行中です。終了するには Ctrl+C を押してください")
        try:
            while True:
                time.sleep(0.1)
                # 全スレッドが終了していたら待機ループを抜ける
                if all(not t.is_alive() for t in self._threads):
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
