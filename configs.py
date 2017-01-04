import os

base_dir = os.path.abspath(os.path.dirname(__file__))
db_url = 'sqlite:////{}'.format(os.path.join(base_dir, 'data-notifier.db'))
log_path = os.path.join(base_dir, 'log.txt')