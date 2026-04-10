"""ZeroMQ REQ-REP 受信スレッド。

外部プロセスからのコマンドを ZeroMQ REP ソケットで受け付け、
CameraStateManager に委譲してレスポンスを返す。

プロトコル:
    リクエスト (JSON): {"command": "CAM_START"}
    レスポンス (JSON): {"status": "ok", "state": "CAM_RUNNING"}
                      {"status": "error", "state": "IDLE", "message": "..."}

使用例（外部クライアント側）:
    import zmq, json
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.connect("tcp://localhost:5556")
    sock.send_string(json.dumps({"command": "CAM_START"}))
    reply = json.loads(sock.recv_string())
"""

import json
import logging
import threading
import traceback

import zmq

from src.control.state import CameraStateManager

logger = logging.getLogger(__name__)


class ZmqReceiver(threading.Thread):
    """ZeroMQ REP ソケットでコマンドを受け付けるスレッド。

    stop_event がセットされると受信ループを終了する。
    """

    def __init__(
        self,
        state_manager: CameraStateManager,
        endpoint: str,
        stop_event: threading.Event,
    ) -> None:
        """
        Args:
            state_manager: コマンドを委譲する状態管理インスタンス
            endpoint: ZeroMQ REP ソケットのバインドアドレス (例: "tcp://*:5556")
            stop_event: 停止フラグ（セットで受信ループ終了）
        """
        super().__init__(name="ZmqReceiver", daemon=True)
        self._state_manager = state_manager
        self._endpoint = endpoint
        self._stop_event = stop_event

    def run(self) -> None:
        context = zmq.Context()
        socket = context.socket(zmq.REP)

        try:
            socket.bind(self._endpoint)
            # ポーリング間隔: stop_event を確認するための受信タイムアウト(ms)
            socket.setsockopt(zmq.RCVTIMEO, 500)
            logger.info(f"ZmqReceiver 開始 → {self._endpoint}")

            while not self._stop_event.is_set():
                try:
                    raw = socket.recv_string()
                except zmq.Again:
                    # タイムアウト: stop_event を確認して続行
                    continue

                response = self._process(raw)
                socket.send_string(json.dumps(response, ensure_ascii=False))

        except Exception:
            logger.error("ZmqReceiver で例外が発生しました")
            traceback.print_exc()
        finally:
            socket.close()
            context.term()
            logger.info("ZmqReceiver 終了")

    def _process(self, raw: str) -> dict:
        """受信メッセージを解析してコマンドを実行し、レスポンス辞書を返す。"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "state": str(self._state_manager.state),
                "message": f"JSON パースエラー: {raw!r}",
            }

        command = data.get("command")
        if not command:
            return {
                "status": "error",
                "state": str(self._state_manager.state),
                "message": "'command' フィールドが見つかりません",
            }

        logger.debug(f"ZmqReceiver: コマンド受信 command={command}")
        return self._state_manager.handle_command(command)
