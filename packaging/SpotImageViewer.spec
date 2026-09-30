import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src', 'core'))
try:
    import config
    APP_VERSION = str(getattr(config, 'CURRENT_VERSION', '20.57'))
except Exception:
    APP_VERSION = '20.57'
APP_NAME = f'SpotImageViewerV{APP_VERSION}'

# Dynamically generate packaging/version.txt from config.CURRENT_VERSION
try:
    parts = APP_VERSION.split('.')
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 20
    minor = int(parts[1][0]) if len(parts) > 1 and len(parts[1]) > 0 and parts[1][0].isdigit() else 5
    build = int(parts[1][1:]) if len(parts) > 1 and len(parts[1]) > 1 and parts[1][1:].isdigit() else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0)
    version_file_content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {build}, 0),
    prodvers=({major}, {minor}, {build}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'WBSEDCL'),
        StringStruct(u'FileDescription', u'Spot Image Viewer and Verification Tool'),
        StringStruct(u'FileVersion', u'{major}.{minor}.{build}'),
        StringStruct(u'InternalName', u'SpotImageViewer'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2026 Pramod Kumar Verma'),
        StringStruct(u'OriginalFilename', u'SpotImageViewerV{APP_VERSION}.exe'),
        StringStruct(u'ProductName', u'Spot Image Viewer'),
        StringStruct(u'ProductVersion', u'{major}.{minor}.{build}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)"""
    with open(os.path.join(SPECPATH, 'version.txt'), 'w', encoding='utf-8') as vf:
        vf.write(version_file_content)
except Exception as e:
    pass


a_main = Analysis(
    [os.path.join(PROJECT_ROOT, 'main_web.py')],
    pathex=[
        PROJECT_ROOT,
        os.path.join(PROJECT_ROOT, 'src'),
        os.path.join(PROJECT_ROOT, 'src', 'core'),
        os.path.join(PROJECT_ROOT, 'src', 'core', 'services'),
        os.path.join(PROJECT_ROOT, 'src', 'bridge'),
    ],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.ico'), 'assets'),
        (os.path.join(PROJECT_ROOT, 'assets', 'spot_icon.png'), 'assets'),
        (os.path.join(PROJECT_ROOT, 'src', 'ui_web'), os.path.join('src', 'ui_web')),
    ],
    hiddenimports=[
        'config',
        'database',
        'utils',
        'tariff_manager',
        'live_osd_service',
        'core',
        'core.config',
        'core.database',
        'core.utils',
        'core.tariff_manager',
        'core.live_osd_service',
        'core.services',
        'core.services.billing_service',
        'core.services.image_service',
        'core.services.fuzzy_service',
        'core.services.consumer_data_service',
        'core.services.audit_service',
        'core.services.folder_service',
        'core.services.update_service',
        'core.services.osd_service',
        'core.services.dcrc_parser',
        'core.services.dcrc_processor',
        'core.services.dcrc_exporter',
        'core.services.spotai_bill_service',
        'core.services.license_service',
        'dcrc_parser',
        'dcrc_processor',
        'dcrc_exporter',
        'spotai_bill_service',
        'license_service',
        'bridge',
        'bridge.app_api',
        'bridge.mixins.spotai_bridge',
        'ui_splash',
        'PIL',
        'openpyxl',
        'requests',
        'packaging',
        'webview',
        'clr',
        'pypdf',
        'thefuzz'
    ],
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
    name=APP_NAME,
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
    hiddenimports=[
        'customtkinter',
        'darkdetect',
        'PIL',
        'requests',
        'tools.meter_audit',
        'tools.meter_audit.constants',
        'tools.meter_audit.client',
        'tools.meter_audit.prefetcher',
        'tools.meter_audit.ui_queue',
        'tools.meter_audit.ui_login',
        'tools.meter_audit.app'
    ],
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
    name=APP_NAME,
)
