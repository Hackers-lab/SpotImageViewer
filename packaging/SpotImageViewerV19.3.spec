# -*- mode: python ; coding: utf-8 -*-
import os

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

a_main = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT, os.path.join(PROJECT_ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.ico'), 'assets'),
        (os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.png'), 'assets'),
    ],
    hiddenimports=['ttkbootstrap', 'PIL', 'openpyxl', 'requests', 'packaging', 'darkdetect', 'customtkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz_main = PYZ(a_main.pure)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name='SpotImageViewerV19.3',
    icon=os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=os.path.join(SPECPATH, 'version.txt'),
)

a_tool = Analysis(
    [os.path.join(PROJECT_ROOT, 'src', 'tools', 'imagecheckgui.py')],
    pathex=[PROJECT_ROOT, os.path.join(PROJECT_ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.ico'), 'assets'),
        (os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.png'), 'assets'),
    ],
    hiddenimports=['customtkinter', 'darkdetect', 'PIL', 'requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz_tool = PYZ(a_tool.pure)

exe_tool = EXE(
    pyz_tool,
    a_tool.scripts,
    [],
    exclude_binaries=True,
    name='imagecheckgui',
    icon=os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_main,
    a_main.binaries,
    a_main.datas,
    exe_tool,
    a_tool.binaries,
    a_tool.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SpotImageViewerV19.3',
)
