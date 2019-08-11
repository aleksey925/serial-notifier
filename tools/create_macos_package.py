"""
Скрипт для создания нативного MacOS приложения, которое можно будет поместить
в папку "Программы" и которое будет отображаться в лаунчере.
"""
import os
import shutil
import stat
import sys
from os.path import join, split, exists, dirname, abspath, realpath

EXCLUDE = [
    '.idea', '.git', 'tools', 'venv', '.gitignore', 'poetry.lock',
    'pyproject.toml', 'README.md', 'setting.conf', 'sites.conf', 'log.txt',
    'data-notifier.db'
]
MACOS_PACKAGE_DIRS = ['Contents/MacOS', 'Contents/Resources']
BASE_DIR = dirname(abspath(__file__))

APP_ROOT_DIR = split(BASE_DIR)[0]
APP_NAME = 'Serial Notifier'
APP_VERSION = open(join(APP_ROOT_DIR, 'version.txt')).read().strip()
APP_ICON_PATH = 'icons/app-icon-512x512.icns'
APP_ENTRY_POINT_SCRIPT = 'serial_notifier.py'
BUNDLE_IDENTIFIER = f'org.{APP_NAME.replace(" " , "").lower()}'

TARGET_DIR = BASE_DIR
TARGET_PACKAGE_PATH = join(TARGET_DIR, APP_NAME + '.app')
TARGET_PATH_RUN_SCRIPT = join(
    TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[0],
    APP_NAME.replace(' ', '').lower() + '.sh'
)
INTERPRETER_SYMLINK_NAME = 'python'


info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDocumentTypes</key>
    <array>
      <dict>
        <key>CFBundleTypeIconFile</key>
        <string>{split(APP_ICON_PATH)[1]}</string>
      </dict>
    </array>
    <key>CFBundleDevelopmentRegion</key>
    <string>English</string>
    <key>CFBundleExecutable</key>
    <string>{split(TARGET_PATH_RUN_SCRIPT)[1]}</string>
    <key>CFBundleGetInfoString</key>
    <string>{APP_NAME} {APP_VERSION}</string>
    <key>CFBundleIconFile</key>
    <string>{split(APP_ICON_PATH)[1]}</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_IDENTIFIER}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>{APP_VERSION}</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleVersion</key>
    <string>{APP_VERSION}</string>
    <key>NSAppleScriptEnabled</key>
    <string>YES</string>
    <key>NSMainNibFile</key>
    <string>MainMenu</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
'''

pkg_info = 'APPL????'

run_sh = '''#!/usr/bin/env bash
export LC_ALL=en_US.UTF-8
ROOT_DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
exec "$ROOT_DIR"/%s "$ROOT_DIR"/%s
''' % (INTERPRETER_SYMLINK_NAME, APP_ENTRY_POINT_SCRIPT)


def get_python_path():
    """
    Вычисляет путь до используемыеого сейчас интерпретатора python. Найденный
    интерпретатор будет использоваться для запуска собранного приложения.
    Важно заметить, что должен использоваться python специально адаптированный
    для MacOS (то есть упакованный в Python.app), иначе настройки из Info.plist
    не применятся корректно. По этому использовать виртуальные окружения или
    python поставленный через brew или pyenv нельзя.
    :return: путь интерпретатора python
    """
    python_base_path, top = split(realpath(sys.executable))
    while top:
        if 'Resources' in python_base_path:
            pass
        elif exists(join(python_base_path, 'Resources')):
            break

        python_base_path, top = split(python_base_path)
    else:
        print(
            f'Не удалось найти дирректорию Resources, которая ассоциирована с '
            f'{sys.executable}'
        )
        sys.exit(1)

    python_path = join(
        python_base_path, 'Resources', 'Python.app', 'Contents', 'MacOS',
        'Python'
    )
    if not exists(python_path):
        print(f'Не удалсь найти Python in Python.app ({python_path})')
        sys.exit(1)

    return python_path


if exists(TARGET_PACKAGE_PATH):
    inp = input(
        'Создаваемое приложение уже существует. Удалить (y/n)? '
    ).lower()
    if inp in ['y', 'yes']:
        shutil.rmtree(TARGET_PACKAGE_PATH)
        print('Старая версия приложения удалена')
    else:
        exit(0)

# Создаем каркас MacOS пакета
os.mkdir(TARGET_PACKAGE_PATH)
for i in MACOS_PACKAGE_DIRS:
    os.makedirs(join(TARGET_PACKAGE_PATH, i), exist_ok=True)

# Копируем файлы приложения в папку, которая будет представлять MacOS пакет
for i in os.listdir(APP_ROOT_DIR):
    if i not in EXCLUDE:
        from_ = join(APP_ROOT_DIR, i)
        if os.path.isdir(from_):
            shutil.copytree(
                from_,
                join(TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[0], i)
            )
        else:
            shutil.copy(
                from_, join(TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[0])
            )

# Копируем иконку приложения в папку с ресурсами
shutil.copy(
    join(APP_ROOT_DIR, APP_ICON_PATH),
    join(TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[1])
)

with open(join(TARGET_PACKAGE_PATH, 'Contents', 'Info.plist'), 'w',
          encoding='utf-8') as out:
    out.write(info_plist)

with open(join(TARGET_PACKAGE_PATH, 'Contents', 'PkgInfo'), 'w',
          encoding='utf-8') as out:
    out.write(pkg_info)

with open(TARGET_PATH_RUN_SCRIPT, 'w', encoding='utf-8') as out:
    out.write(run_sh)

# Создает символическую ссылку на интерпретатор python
os.symlink(
    get_python_path(),
    join(TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[0], INTERPRETER_SYMLINK_NAME)
)

os.chmod(
        TARGET_PATH_RUN_SCRIPT, (os.stat(TARGET_PATH_RUN_SCRIPT).st_mode |
                                 stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
)
