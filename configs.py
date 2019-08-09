import os
import sys
from os.path import abspath, dirname, join, expanduser, exists


def get_resources_dir():
    if os.environ.get('MODE', 'prod') == 'prod':
        path = join(expanduser('~'), '.serial-notifier')
        if not exists(path):
            os.makedirs(path, exist_ok=True)
    else:
        path = abspath(dirname(__file__))

    return path


base_dir = abspath(dirname(__file__))
resources_dir = get_resources_dir()
db_url = 'sqlite:///{}'.format(join(resources_dir, 'data-notifier.db'))
log_path = join(resources_dir, 'log.txt')

app_name = 'Serial Notifier'
app_version = open(join(base_dir, 'version.txt')).read().strip()

# Показыет с использованием какой версии python (нативной для macos или
# установленной через pyenv or brew) запущено проложение
is_native_macos_mode = (
        '.app/Contents' in sys.executable or
        'Python.framework' in sys.executable
)
