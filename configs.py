import os
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

window_title = 'В курсе новых серий'
