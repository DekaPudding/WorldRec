# WorldRec

VRChatの訪問ワールド履歴を自動記録・参照するデスクトップアプリです。

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
