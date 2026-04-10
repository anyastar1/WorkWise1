# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Собираем статические файлы и шаблоны
added_files = [
    ('static', 'static'),
    ('templates', 'templates'),
]

# Добавляем дополнительные данные, если они нужны от библиотек
# Например, для некоторых библиотек могут понадобиться данные
added_files += collect_data_files('flask')

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'routes.auth',
        'routes.main',
        'routes.documents',
        'services.llm_analyzer',
        'services.document_processor',
        'services.error_renderer',
        'database',
        'utils.path_helpers',
        'utils.document_parser.parsers',
        'utils.document_parser.parsers.docx_parser',
        'utils.document_parser.parsers.pdf_parser',
        'utils.document_parser.processors.async_processor',
        'utils.document_parser.processors.cache',
        'utils.document_parser.exporters.llm_exporter',
        'utils.document_parser.models.document',
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
    name='AikorApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
