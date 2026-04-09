import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from src.models.cleaning_session import CleaningSession
from src.models.grid_cell import GridCell

logger = logging.getLogger(__name__)


class DataStorage:
    """清掃セッションデータの永続化を担うクラス。

    セッションデータをJSONファイルに保存し、異常終了時のデータ保全のため都度保存する。
    ヒートマップ画像はPNG形式で同一ディレクトリに保存する。
    """

    BASE_DIR = "logs/sessions"

    def __init__(self) -> None:
        Path(self.BASE_DIR).mkdir(parents=True, exist_ok=True)

    def create_session(self, table_id: str, rows: int = 3, cols: int = 7) -> CleaningSession:
        """新しい清掃セッションを作成する。

        Args:
            table_id: テーブル識別子（例: "table_01"）
            rows: グリッドの行数
            cols: グリッドの列数

        Returns:
            初期化済みの CleaningSession
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now().isoformat()

        grid_cells = [
            [GridCell(row=r, col=c) for c in range(cols)]
            for r in range(rows)
        ]

        session = CleaningSession(
            session_id=session_id,
            table_id=table_id,
            started_at=started_at,
            grid_cells=grid_cells,
        )

        # セッションディレクトリを事前作成
        session_dir = Path(self.BASE_DIR) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        return session

    def save_session(self, session: CleaningSession, heatmap_img: np.ndarray) -> None:
        """清掃セッションデータとヒートマップ画像を保存する。

        都度保存のため、フレームごとに呼び出しても安全。
        保存失敗時はログに記録して処理を継続する（データ保全優先）。

        Args:
            session: 保存する清掃セッション
            heatmap_img: 保存するヒートマップ画像（OpenCV ndarray）
        """
        session_dir = Path(self.BASE_DIR) / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._save_json(session, session_dir)
        except Exception as e:
            logger.error(f"セッションJSON保存失敗 [{session.session_id}]: {e}")

        try:
            heatmap_path = session_dir / "heatmap.png"
            cv2.imwrite(str(heatmap_path), heatmap_img)
        except Exception as e:
            logger.error(f"ヒートマップ画像保存失敗 [{session.session_id}]: {e}")

    def load_session(self, session_id: str) -> CleaningSession | None:
        """保存済みセッションデータを読み込む。

        Args:
            session_id: セッションID（YYYYMMDD_HHMMSS形式）

        Returns:
            読み込んだ CleaningSession、存在しない場合は None
        """
        session_path = Path(self.BASE_DIR) / session_id / "session.json"
        if not session_path.exists():
            return None

        try:
            with open(session_path, encoding="utf-8") as f:
                data = json.load(f)
            return self._dict_to_session(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"セッションJSON読み込み失敗 [{session_id}]: {e}")
            return None

    def _save_json(self, session: CleaningSession, session_dir: Path) -> None:
        """セッションデータをJSONファイルに保存する。"""
        data = {
            "session_id": session.session_id,
            "table_id": session.table_id,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "cleaning_rate": session.cleaning_rate,
            "grid_cells": [
                [
                    {
                        "row": cell.row,
                        "col": cell.col,
                        "accumulated_seconds": cell.accumulated_seconds,
                        "is_cleaned": cell.is_cleaned,
                        "last_hand_detected_at": cell.last_hand_detected_at,
                    }
                    for cell in row
                ]
                for row in session.grid_cells
            ],
        }
        json_path = session_dir / "session.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _dict_to_session(self, data: dict) -> CleaningSession:  # type: ignore[type-arg]
        """辞書データを CleaningSession に変換する。"""
        grid_cells = [
            [
                GridCell(
                    row=cell["row"],
                    col=cell["col"],
                    accumulated_seconds=cell["accumulated_seconds"],
                    is_cleaned=cell["is_cleaned"],
                    last_hand_detected_at=cell.get("last_hand_detected_at"),
                )
                for cell in row
            ]
            for row in data["grid_cells"]
        ]
        return CleaningSession(
            session_id=data["session_id"],
            table_id=data["table_id"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            grid_cells=grid_cells,
            cleaning_rate=data.get("cleaning_rate", 0.0),
        )
