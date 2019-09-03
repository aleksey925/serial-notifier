import logging
import os

from alembic.config import main as alembic_commands

from loggers import root_logger_cleaner


def apply_migrations(root_dir):
    """
    Применяет к текущей БД все миграции
    :param root_dir: корневая дирректория проекта (дирректория в которой
    располагается папка alembic, содержащая миграции)
    """
    cwd = os.getcwd()
    os.chdir(root_dir)
    logger_cleaner = root_logger_cleaner()
    next(logger_cleaner)

    try:
        alembic_commands(argv=('--raiseerr', 'upgrade', 'head',))
    except Exception as err:
        next(logger_cleaner)
        logging.getLogger('serial-notifier').error(
            f'Возникла ошибка при попытке применить миграции: {err}'
        )
        raise
    finally:
        os.chdir(cwd)

    next(logger_cleaner)
