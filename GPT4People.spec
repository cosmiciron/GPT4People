# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/shileipeng/Documents/cosmiciron/GPT4People/channels/matrix/channel.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/shileipeng/Documents/cosmiciron/GPT4People/base', 'base/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/config', 'config/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/core', 'core/')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GPT4People',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GPT4People',
)
