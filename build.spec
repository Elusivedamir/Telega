# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = (
    collect_submodules('telethon')
    + collect_submodules('qasync')
    + collect_submodules('keyring')
    + collect_submodules('PyQt6')
    + collect_submodules('cryptography')  # ✅ Добавили для шифрования
    + ['socks']
)

datas = []
datas += collect_data_files('telethon', include_py_files=True)
datas += collect_data_files('PyQt6')
datas += collect_data_files('keyring')
datas += collect_data_files('cryptography')  # ✅ Добавили

# ✅ ИСПРАВЛЕНИЕ: убрали проблемный файл с невалидным именем
# datas += [('СТЯ  С.md', '.')]  # 🚨 БЫЛО НЕПРАВИЛЬНО

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TelegramAutoBot',
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
    name='TelegramAutoBot',
)

app = BUNDLE(
    coll,
    name='TelegramAutoBot.app',
    icon=None,
    bundle_identifier='com.telegramautobot.app',
    info_plist={
        'CFBundleName': 'TelegramAutoBot',
        'CFBundleDisplayName': 'TelegramAutoBot',
        'CFBundleIdentifier': 'com.telegramautobot.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSBackgroundOnly': False,
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'NSPrincipalClass': 'NSApplication',
    },
)
