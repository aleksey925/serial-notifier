import logging
import threading
from abc import ABCMeta, abstractmethod

import requests
import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtCore
from sip import wrappertype

from config_readers import SerialsUrls
from upgrade_state import UpgradeState


class DIServises(cnt.DeclarativeContainer):
    conf_program = prv.Provider()
    serials_urls = prv.Provider()


def async_thread(my_func):
    """
    Запускает функцию в отдельном потоке
    """
    def wrapper(*args, **kwargs):
        my_thread = threading.Thread(target=my_func, args=args, kwargs=kwargs)
        my_thread.start()
    return wrapper


@async_thread
def get_internet_status(signal):
    logger = logging.getLogger('serial-notifier')
    try:
        requests.get(
            DIServises.conf_program().data['downloader'][
                'check_internet_access_url'
            ],
            timeout=15
        )
        signal.emit(True)
    except Exception as e:
        logger.error('Отстуствует доступ в интернет')
        signal.emit(False)


class BaseDownloaderMetaClass(wrappertype, ABCMeta):
    """
    Нужен для решения конфликта при наследовании двух метаклассов
    """
    pass


class BaseDownloader(QtCore.QObject, metaclass=BaseDownloaderMetaClass):

    s_download_complete = QtCore.pyqtSignal(
        UpgradeState, list, list, dict, name='download_complete'
    )
    s_internet_state = QtCore.pyqtSignal(bool, name='internet_state')

    def __init__(self):
        super().__init__()

        self.target_urls: SerialsUrls = DIServises.serials_urls()
        self.conf_program: dict = DIServises.conf_program().data

        self.s_internet_state.connect(
            self.check_internet_access, QtCore.Qt.QueuedConnection
        )

    @abstractmethod
    def start(self):
        """
        Запускает загрузку информации о новых сериях
        """
        raise NotImplementedError()

    @abstractmethod
    def cancel_download(self):
        """
        Отменяет загрузку
        """
        raise NotImplementedError()

    @abstractmethod
    def clear(self):
        """
        Служит для очистки временных хранилишь с информацией
        """
        raise NotImplementedError()

    def get_internet_status(self):
        """
        Запускает проверку доступен интернет или нет. Результат передается в
        функцию check_internet_access
        """
        get_internet_status(self.s_internet_state)

    @abstractmethod
    def check_internet_access(self, is_available):
        raise NotImplementedError()
