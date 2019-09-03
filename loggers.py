import sys
import logging

import dependency_injector.containers as cnt
import dependency_injector.providers as prv


class DIServices(cnt.DeclarativeContainer):
    unhandled_exception_message_box = prv.Provider()


def unhandled_exception_hook(exc_type, exc_value, exc_traceback):
    logging.getLogger('serial-notifier').error(
        '#CRITICAL Возникла непредвиденная ошибка в работе приложения:',
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    DIServices.unhandled_exception_message_box()()


def root_logger_cleaner():
    """
    Сбрасывает root логгер к настройкам, которые были у root логгера при
    инициализации коррутины
    """
    root = logging.getLogger()
    default_settings = {
        'level': root.level,
        'disabled': root.disabled,
        'propagate': root.propagate,
        'filters': root.filters[:],
        'handlers': root.handlers[:],
    }
    yield

    while True:
        for attr, attr_value in default_settings.items():
            setattr(root, attr, attr_value)
        yield


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
    console_formatter = logging.Formatter(
        '#%(levelname)-s, %(pathname)s, line %(lineno)d: %(message)s'
    )

    # Создаётся обработчик,который будет писать сообщения в файл
    file_handler = logging.FileHandler(path, encoding='UTF-8')
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setFormatter(console_formatter)

    # добавляем обработчики в logger
    log.addHandler(file_handler)
    log.addHandler(console_handler)

    sys.excepthook = unhandled_exception_hook
