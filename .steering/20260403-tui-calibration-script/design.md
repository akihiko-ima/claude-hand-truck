# 設計書

## ライブラリ選定

`rich` を採用する。理由:
- OpenCV のウィンドウループと競合しない（TUI 専用スレッドが不要）
- `Console`, `Panel`, `Status`, `Table`, `Rule` だけで十分なUXが実現できる
- `textual` は非同期イベントループが必要なため OpenCV との同時使用が複雑

## コンポーネント設計

### Console インスタンス

スクリプト全体で `console = Console()` を1つ共有する。

### 各箇所の置き換え方針

| 現在 | rich 置き換え |
|------|--------------|
| `print("=== タイトル ===")` | `console.print(Panel(..., style="bold cyan"))` |
| `print("カメラ起動中...")` | `with console.status("カメラ起動中...", spinner="dots"):` |
| `print(f"エラー: ...")` | `console.print(f"[bold red]エラー: ...[/]")` |
| `print("操作手順")` | `console.print(Panel(手順テキスト, title="操作手順"))` |
| `print("完了")` | `console.print(Panel(Table(保存パス), style="green"))` |

## データフロー（変更なし）

UI 層の変更のみ。ロジック・フローは変更しない。

## ディレクトリ構造

```
pyproject.toml              ← rich 依存追加
scripts/setup_calibration.py ← rich 導入
```

## 実装の順序

1. `pyproject.toml` に `rich>=13.0` を追加して `uv sync`
2. `setup_calibration.py` の import に rich を追加
3. `main()` のタイトル表示を Panel に置き換え
4. `_capture_frame()` の呼び出し部分を Status スピナーで囲む
5. `_calibrate_camera()` の print を Panel + colored text に置き換え
6. `_show_blend_preview()` の print を Panel に置き換え
7. 保存完了メッセージを Table + Panel に置き換え
8. エラーメッセージを `[bold red]` に置き換え
