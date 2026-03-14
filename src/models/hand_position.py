from dataclasses import dataclass


@dataclass
class HandPosition:
    """検出された手の位置情報を表すデータクラス。

    テーブル正規化座標系（左上=0,0 / 右下=1,1）での位置を保持する。
    """

    x_normalized: float  # テーブル座標系でのX位置 (0.0-1.0, 左端=0)
    y_normalized: float  # テーブル座標系でのY位置 (0.0-1.0, 上端=0)
    timestamp: float     # 検出時のUnixタイムスタンプ
    camera_id: int       # 検出したカメラのID (0 or 1)
    confidence: float    # 検出信頼度 (0.0-1.0)
