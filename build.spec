# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配方 — 输出为一个独立文件夹，可直接分发"""

import os
import sys
from pathlib import Path

_PROJ = Path(".").resolve()

a = Analysis(
    ["app.py"],
    pathex=[str(_PROJ)],
    binaries=[],
    datas=[
        ("templates", "templates"),
        ("config.yaml", "."),
    ],
    hiddenimports=[
        "flask",
        "flask.json",
        "jinja2",
        "jinja2.ext",
        "markupsafe",
        "yaml",
        "playwright",
        "playwright.async_api",
        "playwright._impl",
        "playwright._impl._api_types",
        "playwright._impl._browser",
        "playwright._impl._browser_context",
        "playwright._impl._page",
        "greenlet",
        "pyee",
        "pyee.asyncio",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "cv2",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="小红书热点收集器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version_info=None,
)
