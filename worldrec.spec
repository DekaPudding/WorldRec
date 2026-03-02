# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# PyInstaller executes spec files via `exec()` and `__file__` may be undefined.
# Prefer `SPEC` injected by PyInstaller; fallback keeps local/manual execution working.
project_root = Path(globals().get("SPEC", Path.cwd() / "worldrec.spec")).resolve().parent

block_cipher = None

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "scripts" / "*.ps1"), "scripts")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WorldRec",
    icon="NONE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WorldRec",
)
