# タスクリスト

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

---

## フェーズ1: 依存追加

- [x] `pyproject.toml` に `rich>=13.0` を追加
- [x] `uv sync` で依存をインストール

## フェーズ2: setup_calibration.py の TUI 化

- [x] rich の import を追加し `console = Console()` を定義
- [x] `main()` タイトルを Panel に置き換え
- [x] カメラ初期化を `console.status` スピナーで囲む
- [x] `_calibrate_camera()` の print を Panel + colored text に置き換え
- [x] `_show_blend_preview()` の print を Panel に置き換え
- [x] 保存完了メッセージを Table + Panel に置き換え
- [x] エラーメッセージを `[bold red]` スタイルに置き換え

## フェーズ3: 動作確認

- [x] 構文チェック（`python -c "import ast; ast.parse(...)"`)
- [x] `python scripts/setup_calibration.py --help` 相当で import エラーがないことを確認

## フェーズ4: 振り返り

- [x] 実装後の振り返りを記録

---

## 実装後の振り返り

### 実装完了日
2026-04-03

### 計画と実績の差分

**計画と異なった点**:
- 特になし。設計どおりに実装できた。

### 学んだこと
- `rich` の `Table.grid()` を使うとキーバインド一覧などをきれいに並べられる
- `console.status()` は `with` ブロックを抜けると自動的にスピナーが消える

### 次回への改善提案
- `src/main.py` の起動メッセージにも rich を導入すると一貫性が出る
