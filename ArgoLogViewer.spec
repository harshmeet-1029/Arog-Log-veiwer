# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# Platform-specific settings
if sys.platform == 'darwin':  # macOS
    icon_file = 'app/icon.icns'
    separator = '/'
elif sys.platform == 'win32':  # Windows
    icon_file = 'app/icon.ico'
    separator = '\\'
else:  # Linux
    icon_file = 'app/ICON.png'
    separator = '/'

a = Analysis(
    [f'app{separator}main.py'],
    pathex=[],
    binaries=[],
    datas=[(f'app{separator}ICON.png', 'app'), (f'app{separator}*.ico', 'app')],
    hiddenimports=['PySide6', 'paramiko', 'cryptography', 'packaging'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Check if icon file exists, if not use None
icon_path = icon_file if os.path.exists(icon_file) else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArgoLogViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='ArgoLogViewer.app',
        icon=icon_path,
        bundle_identifier='com.harshmeet.argologviewer',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
        },
    )
