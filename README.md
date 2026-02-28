# WorldRec

VRChatの訪問ワールド履歴を自動記録・参照するデスクトップアプリです。

## 公開範囲
このリポジトリはアプリ本体と実行・ビルドに必要な最小構成のみ公開します。
ローカル作業データや詳細ドキュメントは公開対象外です。

## セットアップ
```bash
python -m venv .venv
```

PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

## Windowsビルド
```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\build-exe.ps1 -Clean
```

## リリースビルド
```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\build-release.ps1 -Version 1.0.0 -Clean
```
