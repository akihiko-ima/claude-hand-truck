"""状態管理モジュール。

カメラ・骨格検出プロセスの状態を管理し、外部コマンドに応じて
HandDetectionPipeline のライフサイクルを制御する。

状態遷移:
    IDLE        → INIT      → INITIALIZED
    INITIALIZED → CAM_START → CAM_RUNNING
    CAM_RUNNING → MP_START  → RUNNING
    RUNNING     → MP_STOP   → CAM_RUNNING
    CAM_RUNNING | RUNNING → CAM_STOP → INITIALIZED
    any         → FINALIZE  → IDLE
    any         → STATUS    → same (状態を返すのみ)
"""

import logging
import threading
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app_config import AppConfig
    from src.detection.calibration_manager import CalibrationManager
    from src.models.calibration_config import CalibrationConfig
    from src.pipeline.pipeline import HandDetectionPipeline

logger = logging.getLogger(__name__)


# =========================
# コマンド定義
# =========================
class Command(StrEnum):
    INIT = "INIT"
    CAM_START = "CAM_START"
    CAM_STOP = "CAM_STOP"
    MP_START = "MP_START"
    MP_STOP = "MP_STOP"
    FINALIZE = "FINALIZE"
    STATUS = "STATUS"


# =========================
# 状態定義
# =========================
class AppState(StrEnum):
    IDLE = "IDLE"                   # 未初期化
    INITIALIZED = "INITIALIZED"     # 設定・キャリブ済み、スレッド未起動
    CAM_RUNNING = "CAM_RUNNING"     # カメラスレッド起動中、MP無効
    RUNNING = "RUNNING"             # カメラ + MP 起動中
    ERROR = "ERROR"                 # エラー状態（FINALIZE で IDLE に戻る）


# 有効な状態遷移テーブル: {(current_state, command): next_state}
_TRANSITIONS: dict[tuple[AppState, Command], AppState] = {
    (AppState.IDLE,        Command.INIT):      AppState.INITIALIZED,
    (AppState.INITIALIZED, Command.CAM_START): AppState.CAM_RUNNING,
    (AppState.CAM_RUNNING, Command.MP_START):  AppState.RUNNING,
    (AppState.RUNNING,     Command.MP_STOP):   AppState.CAM_RUNNING,
    (AppState.CAM_RUNNING, Command.CAM_STOP):  AppState.INITIALIZED,
    (AppState.RUNNING,     Command.CAM_STOP):  AppState.INITIALIZED,
    # FINALIZE はどの状態からでも IDLE へ
    (AppState.IDLE,        Command.FINALIZE):  AppState.IDLE,
    (AppState.INITIALIZED, Command.FINALIZE):  AppState.IDLE,
    (AppState.CAM_RUNNING, Command.FINALIZE):  AppState.IDLE,
    (AppState.RUNNING,     Command.FINALIZE):  AppState.IDLE,
    (AppState.ERROR,       Command.FINALIZE):  AppState.IDLE,
}


class CameraStateManager:
    """カメラ・骨格検出プロセスの状態管理クラス。

    HandDetectionPipeline のライフサイクルをコマンドで制御する。
    スレッドセーフ（内部で Lock を使用）。

    使用例:
        manager = CameraStateManager(config, calib_manager, calibrations)
        manager.handle_command("INIT")
        manager.handle_command("CAM_START")
        manager.handle_command("MP_START")
        # ... 処理 ...
        manager.handle_command("FINALIZE")
    """

    def __init__(
        self,
        config: "AppConfig",
        calib_manager: "CalibrationManager",
        calibrations: "dict[int, CalibrationConfig]",
        table_id: str = "table_01",
        debug_mode: bool = False,
        log_mode: bool = False,
    ) -> None:
        """
        Args:
            config: アプリケーション設定
            calib_manager: キャリブレーションマネージャー
            calibrations: {camera_id: CalibrationConfig} の辞書
            table_id: 清掃セッションに紐づくテーブル識別子
            debug_mode: デバッグ画像保存フラグ
            log_mode: キューサイズログ出力フラグ
        """
        self._config = config
        self._calib_manager = calib_manager
        self._calibrations = calibrations
        self._table_id = table_id
        self._debug_mode = debug_mode
        self._log_mode = log_mode

        self._state = AppState.IDLE
        self._lock = threading.Lock()
        self._pipeline: "HandDetectionPipeline | None" = None
        self._drain_timer: threading.Timer | None = None  # MP_STOP 後のキュードレインタイマー

    # ------------------------------------------------------------------
    # パブリックAPI
    # ------------------------------------------------------------------

    @property
    def state(self) -> AppState:
        with self._lock:
            return self._state

    def handle_command(self, command: str) -> dict:
        """コマンドを処理し、レスポンス辞書を返す。

        Args:
            command: Command StrEnum の値文字列

        Returns:
            {"status": "ok", "state": "..."} または
            {"status": "error", "state": "...", "message": "..."}
        """
        try:
            cmd = Command(command.upper())
        except ValueError:
            with self._lock:
                current = self._state
            return self._error(f"未知のコマンド: {command!r}", current)

        with self._lock:
            if cmd == Command.STATUS:
                return self._status_response()

            next_state = _TRANSITIONS.get((self._state, cmd))
            if next_state is None:
                return self._error(
                    f"無効な遷移: state={self._state} + command={cmd}",
                    self._state,
                )

            try:
                self._execute(cmd, next_state)
            except Exception as e:
                logger.exception(f"コマンド {cmd} の実行中にエラーが発生しました")
                self._state = AppState.ERROR
                return self._error(str(e), AppState.ERROR)

            return {"status": "ok", "state": str(self._state)}

    # ------------------------------------------------------------------
    # プライベート: コマンド実行
    # ------------------------------------------------------------------

    def _execute(self, cmd: Command, next_state: AppState) -> None:
        """コマンドを実行し state を更新する（Lock 内から呼び出すこと）。"""
        if cmd == Command.INIT:
            self._do_init()
        elif cmd == Command.CAM_START:
            self._do_cam_start()
        elif cmd == Command.MP_START:
            self._do_mp_start()
        elif cmd == Command.MP_STOP:
            self._do_mp_stop()
        elif cmd == Command.CAM_STOP:
            self._do_cam_stop()
        elif cmd == Command.FINALIZE:
            self._do_finalize()

        self._state = next_state

    def _do_init(self) -> None:
        """INIT: 設定・キャリブレーションの検証。"""
        if not self._calibrations:
            raise RuntimeError("キャリブレーション設定がロードされていません")
        logger.info("CameraStateManager: INIT 完了")

    def _do_cam_start(self) -> None:
        """CAM_START: パイプラインをカメラのみモードで起動。"""
        from src.pipeline.pipeline import HandDetectionPipeline

        self._pipeline = HandDetectionPipeline(
            config=self._config,
            calib_manager=self._calib_manager,
            calibrations=self._calibrations,
            table_id=self._table_id,
            debug_mode=self._debug_mode,
            log_mode=self._log_mode,
        )
        self._pipeline.start(detection_enabled=False)
        logger.info("CameraStateManager: CAM_START 完了 (MP無効)")

    def _do_mp_start(self) -> None:
        """MP_START: 手検出を有効化。"""
        if self._pipeline is None:
            raise RuntimeError("パイプラインが起動していません")
        self._pipeline.enable_detection()
        logger.info("CameraStateManager: MP_START 完了")

    def _do_mp_stop(self) -> None:
        """MP_STOP: 手検出を無効化。5秒後に残存キューを破棄する。"""
        if self._pipeline is None:
            raise RuntimeError("パイプラインが起動していません")
        self._pipeline.disable_detection()
        self._schedule_drain()
        logger.info("CameraStateManager: MP_STOP 完了（5秒後にキューをドレイン）")

    def _do_cam_stop(self) -> None:
        """CAM_STOP: パイプラインを停止。ドレインタイマーもキャンセル。"""
        self._cancel_drain()
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None
        logger.info("CameraStateManager: CAM_STOP 完了")

    def _do_finalize(self) -> None:
        """FINALIZE: パイプラインを停止し全リソースを解放。ドレインタイマーもキャンセル。"""
        self._cancel_drain()
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None
        logger.info("CameraStateManager: FINALIZE 完了")

    # ------------------------------------------------------------------
    # プライベート: ドレインタイマー管理
    # ------------------------------------------------------------------

    _DRAIN_DELAY_SECONDS = 5.0

    def _schedule_drain(self) -> None:
        """5秒後にキュードレインを実行するタイマーをセットする（Lock 内から呼ぶこと）。"""
        self._cancel_drain()
        pipeline = self._pipeline

        def _drain() -> None:
            if pipeline is not None:
                pipeline.drain_queues()
                logger.info("CameraStateManager: キュードレイン完了")

        self._drain_timer = threading.Timer(self._DRAIN_DELAY_SECONDS, _drain)
        self._drain_timer.daemon = True
        self._drain_timer.start()

    def _cancel_drain(self) -> None:
        """未実行のドレインタイマーをキャンセルする（Lock 内から呼ぶこと）。"""
        if self._drain_timer is not None:
            self._drain_timer.cancel()
            self._drain_timer = None

    # ------------------------------------------------------------------
    # プライベート: レスポンス生成
    # ------------------------------------------------------------------

    def _status_response(self) -> dict:
        """STATUS レスポンスを返す（Lock 内から呼び出すこと）。"""
        return {
            "status": "ok",
            "state": str(self._state),
            "pipeline_running": self._pipeline is not None,
        }

    def _error(self, message: str, current_state: AppState) -> dict:
        logger.warning(f"コマンドエラー: {message}")
        return {
            "status": "error",
            "state": str(current_state),
            "message": message,
        }
