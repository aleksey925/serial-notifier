import logging

from PyQt4 import QtGui


def create_logger(path, system_tray: QtGui.QSystemTrayIcon):
    """
    Создаёт объект, который отвечат за логирование

    :argument path: str Путь в который будут писаться логи
    """
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    # Определяется формат логов и добавляется к обработчику
    file_formatter = logging.Formatter(
        '#%(levelname)-s [%(asctime)s]  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(('#%(levelname)-s, line %(lineno)d:'
                                           ' %(message)s'))

    # Создаётся обработчик,который будет писать сообщения в файл
    file_handler = logging.FileHandler(path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)

    system_tray_handler = logging.Handler()
    system_tray_handler.emit = lambda record: system_tray.showMessage(
        'Ошибка', system_tray_handler.format(record)
    )
    system_tray_handler.setLevel(logging.ERROR)

    # добавляем обработчики в _logger
    log.addHandler(file_handler)
    log.addHandler(console_handler)
    log.addHandler(system_tray_handler)

    return log
