# WorldRec

VRChat の訪問ワールド履歴を自動で記録・検索する、Windows 向けデスクトップアプリです。

## 概要

WorldRec は VRChat のログ（`output_log_*.txt`）を監視し、訪問したワールド情報をローカル DB に保存します。履歴の絞り込み表示、ワールド詳細表示、メモ/タグ管理、バックアップ/復元が可能です。

## 主な機能

- VRChat ログ監視による訪問履歴の自動記録
- 日付・期間・クイックフィルタ（今日/昨日/全件）での絞り込み
- ワールド詳細表示（名前、説明、サムネイル、訪問回数など）
- AI検索（OpenAI 利用時は AI 推薦、未設定時は履歴ベース候補）
- メモ/タグの保存
- 設定管理（テーマ、文字サイズ、保存間隔など）
- 設定と DB のバックアップ/復元
- Windows タスクスケジューラを使った自動起動設定

## 動作環境

- OS: Windows（通常利用想定）
- Python: 3.10 以上推奨
- 主な依存ライブラリ:
  - `PySide6==6.7.0`
  - `watchdog==4.0.0`

## インストール

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 起動方法

```powershell
python -m app.main
```

起動オプション:
- `--start-minimized`: 最小化状態で起動

## 使い方

1. アプリを起動すると履歴一覧が表示されます。
2. 日付フィルタで期間を絞り込みます。
3. 履歴行をダブルクリックするとワールド詳細を確認できます。
4. 詳細画面でメモ/タグを編集して保存できます。
5. `AI検索を開く` から検索条件を入力すると、訪問履歴から候補を表示できます。

## 設定とデータ保存先

既定の保存先（Windows）:
- 設定ファイル: `%LOCALAPPDATA%\WorldRec\settings.json`
- データベース: `%LOCALAPPDATA%\WorldRec\worldrec.db`
- VRChat ログ既定参照先: `%USERPROFILE%\AppData\LocalLow\VRChat\VRChat`

## データと通信について

- ローカル保存:
  - VRChat ログから抽出した訪問履歴（ワールド名、訪問時刻など）
  - ユーザーが入力したメモ/タグ
  - アプリ設定（テーマ、ログフォルダ、DBパスなど）
- 外部通信:
  - ワールド詳細表示時に VRChat API（`https://api.vrchat.cloud/api/1`）へ問い合わせ
  - AI検索で `WORLDREC_OPENAI_API_KEY` または `OPENAI_API_KEY` が設定されている場合のみ OpenAI API（`https://api.openai.com/v1`）へ問い合わせ
- 認証情報:
  - VRChat ログイン用パスワードは送信時のみメモリ上で使用し、恒久保存しません
  - APIキーは環境変数から読み取り、アプリ設定ファイルには保存しません

AI検索補足:
- OpenAI API キー未設定でも、保存済みの訪問履歴から候補を表示できます。
- OpenAI API キーを使う場合は、起動前に `WORLDREC_OPENAI_API_KEY` または `OPENAI_API_KEY` を設定してください。
- OpenAI 利用時は、候補一覧とユーザー要望をまとめて送信し、構造化出力で候補番号と理由を受け取ります。

## テスト

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## VRChat 連動の自動起動（Windows）

登録:

```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\register-startup-task.ps1 -PollSeconds 60
```

解除:

```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\unregister-startup-task.ps1
```

補足:
- 旧方式（`powershell.exe ... worldrec-vrchat-autostart.ps1 -PollSeconds 60`）のタスクが残っている場合、PC 起動時にコンソールが表示されることがあります。
- `schtasks /Delete` で「アクセスが拒否されました」が出る場合は、管理者権限の PowerShell/CMD で実行してください。

## ビルド

実行ファイル作成:

```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\build-exe.ps1 -Clean
```

補足:
- 既定の出力先は `.\dist\WorldRec`
- `dist` がロックされている場合は自動で `.\dist_build\WorldRec` に退避してビルド
- 出力先を固定したい場合は `-DistPath` を指定

```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\build-exe.ps1 -Clean -DistPath .\dist_build
```

## ディレクトリ構成

```text
.
├─ app/            # アプリ本体（GUI / core / db / models）
├─ tests/          # 単体テスト
├─ scripts/        # ビルド・自動起動関連の PowerShell スクリプト
├─ worldrec.spec   # PyInstaller 設定
└─ README.md
```

## トラブルシュート

- 履歴が増えない:
  - VRChat が起動中か確認
  - ログフォルダ設定が正しいか確認
  - `output_log_*.txt` が存在するか確認
- ワールド詳細が取得できない:
  - ネットワーク接続を確認
  - VRChat API 認証が必要なケースを確認
- 自動起動しない:
  - タスクスケジューラに `WorldRec-VRChat-Autostart` があるか確認

## ライセンス

このプロジェクトは [MIT License](./LICENSE) の下で公開されています。
