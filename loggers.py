import sys
import logging


def unhandled_exception_hook(exc_type, exc_value, exc_traceback):
    logging.getLogger('serial-notifier').error(
        '#CRITICAL Возникла непредвиденная ошибка в работе приложения:',
        exc_info=(exc_type, exc_value, exc_traceback)
    )


def init_logger(path):
    """
    Инициализирует логгер, включает логгирование не перехваченных исключений
    :param path: str путь к файлу с логами
    """
    log = logging.getLogger('serial-notifier')
    log.setLevel(logging.INFO)

    # Определяется формат логов и добавляется к обработчику
    file_formatter = logging.Formatter(
        ('#%(levelname)-s, %(pathname)s, line %(lineno)d, [%(asctime)s]: '
         '%(message)s'), datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(('#%(levelname)-s, %(pathname)s, '
                                           'line %(lineno)d: %(message)s'))

    # Создаётся обработчик,который будет писать сообщения в файл
    file_handler = logging.FileHandler(path, encoding='UTF-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # system_tray_handler = logging.Handler()
    # system_tray_handler.emit = lambda record: system_tray.showMessage(
    #     'Ошибка', system_tray_handler.format(record)
    # )
    # system_tray_handler.setLevel(logging.ERROR)

    # добавляем обработчики в _logger
    log.addHandler(file_handler)
    log.addHandler(console_handler)
    # log.addHandler(system_tray_handler)

    sys.excepthook = unhandled_exception_hook
