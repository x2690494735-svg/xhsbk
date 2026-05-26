# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

p_bins, p_datas, p_hidden = collect_all("playwright")
g_bins, g_datas, g_hidden = collect_all("greenlet")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=p_bins + g_bins,
    datas=[
        ("templates", "templates"),
        ("config.yaml", "."),
    ] + p_datas + g_datas,
    hiddenimports=[
        "flask",
        "flask.json",
        "jinja2",
        "jinja2.ext",
        "markupsafe",
        "yaml",
        "greenlet",
        "pyee",
        "pyee.asyncio",
    ] + p_hidden + g_hidden,
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
    name="xhs-hot",
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
