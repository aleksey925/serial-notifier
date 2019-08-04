"""
Скрипт для создания нативного MacOS приложения, которое можно будет поместить
в папку "Программы" и которое будет отображаться в лаунчере
"""
import os
import shutil
from os.path import join, split, exists, expanduser, dirname, abspath

EXCLUDE = [
    '.idea', '.git', 'utils', 'poetry.lock', 'pyproject.toml' 'README.md',
    'setting.conf', 'sites.conf', 'log.txt', 'data-notifier.db'
]
MACOS_PACKAGE_DIRS = ['Contents/MacOS', 'Contents/Resources']
PROJECT_ROOT_DIR = split(dirname(abspath(__file__)))[0]
HOME_DIR = expanduser('~')

SOURCE_ROOT_DIR = PROJECT_ROOT_DIR
APP_NAME = 'Serial Notifier'
APP_VERSION = open(join(SOURCE_ROOT_DIR, 'version.txt')).read().strip()
ICON_PATH = 'icons/app-icon-512x512.icns'
ENTRY_POINT_SCRIPT = 'serial_notifier.py'

TARGET_DIR = HOME_DIR
TARGET_PACKAGE_PATH = join(TARGET_DIR, APP_NAME + '.app')
TARGET_PATH_RUN_SCRIPT = join(
    TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[0], APP_NAME.replace(' ', '').lower()
)

info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CFBundleDocumentTypes</key>
    <array>
      <dict>
        <key>CFBundleTypeIconFile</key>
        <string>{split(ICON_PATH)[1]}</string>
      </dict>
    </array>
    <key>CFBundleExecutable</key>
    <string>{APP_NAME.replace(' ', '').lower()}</string>
    <key>CFBundleIconFile</key>
    <string>{split(ICON_PATH)[1]}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleShortVersionString</key>
    <string>{APP_VERSION}</string>
  </dict>
</plist>
'''

run_sh = '''#!/usr/bin/env bash
export LC_ALL=en_US.UTF-8
ROOT_DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$ROOT_DIR"
./venv/bin/python3 ./%s
''' % ENTRY_POINT_SCRIPT


def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2
    os.chmod(path, mode)


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

if 'venv' not in os.listdir(SOURCE_ROOT_DIR):
    print(
        'Необходимо в корне папки с проектом создать виртуальное окружение и '
        'установить туда все необходимые библиотеки.'
    )
    exit(1)

# Копируем файлы приложения в папку, которая будет представлять MacOS пакет
for i in os.listdir(SOURCE_ROOT_DIR):
    if i not in EXCLUDE:
        from_ = join(SOURCE_ROOT_DIR, i)
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
    join(SOURCE_ROOT_DIR, ICON_PATH),
    join(TARGET_PACKAGE_PATH, MACOS_PACKAGE_DIRS[1])
)

with open(join(TARGET_PACKAGE_PATH, 'Contents', 'Info.plist'), 'w') as out:
    out.write(info_plist)

with open(TARGET_PATH_RUN_SCRIPT, 'w') as out:
    out.write(run_sh)

make_executable(TARGET_PATH_RUN_SCRIPT)
