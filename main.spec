# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('/Users/shileipeng/Documents/cosmiciron/GPT4People/base', 'base/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/channels', 'channels/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/config', 'config/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/core', 'core/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/llama.cpp-master', 'llama.cpp-master/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/llm', 'llm/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/memory', 'memory/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/models', 'models/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/plugins', 'plugins/'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/main.py', '.'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/LICENSE', '.'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/requirements.txt', '.'), ('/Users/shileipeng/Documents/cosmiciron/GPT4People/main.py', '.')]
datas += collect_data_files('chromadb')


a = Analysis(
    ['/Users/shileipeng/Documents/cosmiciron/GPT4People/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['ONNXMiniLM_L6_V2', 'transformer'],
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
    name='main',
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
    name='main',
)
