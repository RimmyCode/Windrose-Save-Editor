# windrose.spec — PyInstaller build spec for Windrose Save Editor
# Build with: pyinstaller --clean windrose.spec
# Output:     dist/Windrose Save Editor/  (onedir, console)
import os
import sys

block_cipher = None

# Include native RocksDB libraries if present at build time
binaries = []
for lib in ['rocksdb.dll', 'librocksdb.so']:
    if os.path.exists(lib):
        binaries.append((lib, '.'))

# Bundle data files users expect alongside the exe
datas = []
for f in ['Item ID Database.html', 'GUIDE.md']:
    if os.path.exists(f):
        datas.append((f, '.'))

a = Analysis(
    ['windrose_save_editor/__main__.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
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
    name='Windrose Save Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Windrose Save Editor',
)
