# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Collect all asset files
def collect_assets():
    assets = []
    assets_dir = os.path.join(os.getcwd(), 'assets')
    for root, dirs, files in os.walk(assets_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_dir = os.path.relpath(root, os.getcwd())
            assets.append((full_path, rel_dir))
    return assets

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=collect_assets(),
    hiddenimports=[
        'websockets',
        'websockets.legacy',
        'websockets.legacy.server',
        'websockets.legacy.client',
        'websockets.connection',
        'pygame',
        'pygame.mixer',
        'PIL',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Garlic Phone',
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
    icon='assets/icons/thumbnail.png',
    onefile=True,
)