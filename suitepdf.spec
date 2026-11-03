# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['PIL', 'pymupdf', 'fitz', 'src', 'src.compressor', 'src.merger', 'src.gui']

tmp_ctk = collect_all('customtkinter')
datas += tmp_ctk[0]
binaries += tmp_ctk[1]
hiddenimports += tmp_ctk[2]

tmp_pymupdf = collect_all('pymupdf')
datas += tmp_pymupdf[0]
binaries += tmp_pymupdf[1]
hiddenimports += tmp_pymupdf[2]

# Inclui os ativos de imagem e ícone oficial
datas += [('assets/app_icon.png', 'assets'), ('assets/app_icon.ico', 'assets')]

a = Analysis(
    ['src/main.py'],
    pathex=['.', 'src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='SuitePDF',
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
    icon=['assets/app_icon.ico'],
)

