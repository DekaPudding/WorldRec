# WorldRec ユーザーガイド

VRChatの訪問ワールド履歴を自動記録・参照するデスクトップアプリです。

- 最終更新: 2026-03-01
- 対象: WorldRecを日常利用するユーザー

## このアプリでできること
- VRChatの訪問ワールド履歴を自動で記録
- 履歴を日付で絞り込んで確認
- ワールド行をダブルクリックして詳細表示
- 設定画面から見た目や記録動作を調整

注意:
- AI検索機能は現在未実装です（画面上でも未実装と表示されます）。

## 初回セットアップ

### 1) インストール
```bash
python -m venv .venv
```

PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) 起動
```bash
python -m app.main
```

## 基本的な使い方

### 履歴を見る
- アプリ起動後、履歴一覧が表示されます。
- 一覧には主に「時刻」「ワールド名」「インスタンスタイプ」が表示されます。

### 日付で絞り込む
- 単日: カレンダーの日付をダブルクリック
- 期間: 「期間」モードで開始/終了日時を入力して「適用」
- クイック: 「今日」「昨日」「クリア」

### ワールド詳細を開く
- 一覧の行をダブルクリック
- 詳細ダイアログで次の情報を確認できます。
  - ワールド名
  - 総訪問回数
  - インスタンスタイプ
  - ワールド容量
  - 対応Platform
  - 説明
  - サムネイル
  - メモ/タグ

### メモ/タグを保存する
- 詳細ダイアログのメモとタグを編集
- 「メモ/タグを保存」を押す

## 設定画面の使い方

### 開き方
- メニュー `設定 > 設定を開く...`
- または `Ctrl+,`

### タブ構成
- 基本設定
  - テーマ（システム/ライト/ダーク）
  - 文字サイズ（標準/大きめ）
  - 起動時に表示する期間（今日/昨日/全件）
  - AI検索は未実装案内のみ
- 詳細設定
  - VRChatログフォルダ
  - データベース保存先
  - 保存の間隔（秒）
  - まとめて保存する件数
  - 自動起動タスク登録/解除（Windows）
- データ管理
  - バックアップ作成
  - バックアップ復元
  - 設定のみ初期化

### ボタンの意味
- `OK`: 保存して閉じる
- `適用`: 保存して閉じない
- `キャンセル`: 変更を破棄
- `初期値に戻す`: 現在のタブを初期値に戻す

### いつ反映されるか
すぐ反映:
- テーマ
- 文字サイズ
- 保存の間隔
- まとめて保存する件数
- VRChatログフォルダ

次回起動で反映:
- 起動時に表示する期間
- データベース保存先

## バックアップと復元

### バックアップ
- 設定画面 > データ管理 > 「バックアップを作成...」
- `settings.json` と `worldrec.db` をZIPで保存します。

### 復元
- 設定画面 > データ管理 > 「バックアップから復元...」
- 現在の設定とDBを上書きします（確認ダイアログあり）。

## VRChat連動の自動起動（Windows）

設定画面から操作できるほか、手動でも実行できます。

登録:
```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\register-startup-task.ps1 -PollSeconds 60
```

解除:
```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\unregister-startup-task.ps1
```

## よくある確認ポイント
- 履歴が増えない
  - VRChatを起動しているか
  - ログフォルダ設定が正しいか（設定画面 > 詳細設定）
  - `output_log_*.txt` が存在するか
- 詳細が取得できない
  - 通信状況
  - VRChat API認証が必要なケース
- 自動起動しない
  - タスクスケジューラに `WorldRec-VRChat-Autostart` があるか

## 保存先（Windows）
- 設定ファイル: `%LOCALAPPDATA%/WorldRec/settings.json`
- DB（既定）: `%LOCALAPPDATA%/WorldRec/worldrec.db`

## 開発者向け（ビルド）

通常利用には不要です。配布用ビルドを作る場合に使います。

Windowsビルド:
```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\build-exe.ps1 -Clean
```

リリースビルド:
```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\build-release.ps1 -Version 1.0.0 -Clean
```
