import logging
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


class BaseDownloaderMetaClass(wrappertype, ABCMeta):
    """
    Нужен для решения конфликта при наследовании двух метаклассов
    """
    pass


class BaseDownloader(QtCore.QObject, metaclass=BaseDownloaderMetaClass):

    s_download_complete = QtCore.pyqtSignal(
        UpgradeState, list, dict, dict, name='download_complete'
    )

    def __init__(self):
        super().__init__()

        self.target_urls: SerialsUrls = DIServises.serials_urls()
        self.conf_program: dict = DIServises.conf_program().data
        self._internet_status_checker = InternetStatusChecker()
        self._logger = logging.getLogger('serial-notifier')

        self._urls_errors = {}
        self._error_msgs = []
        self._downloaded_pages = {}

        self._internet_status_checker.s_internet_state.connect(
            self._start, QtCore.Qt.QueuedConnection
        )

    def start_download(self):
        """
        Запускает загрузку информации о новых сериях
        """
        self._before_start()
        self._internet_status_checker.check()

    def _before_start(self):
        pass

    @abstractmethod
    def _start(self, internet_available: bool):
        """
        Запускает скачивание если интернет доступен
        :param internet_available: логический параметр отражающий доступность
        интернета
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
        Очищает структуры данных используемые downloader`ом
        """
        raise NotImplementedError()


class InternetStatusChecker(QtCore.QThread):

    s_internet_state = QtCore.pyqtSignal(bool, name='internet_state')

    def __init__(self):
        super().__init__()
        self.f_stop = False

    def check(self):
        self.start()

    def run(self):
        self.f_stop = False

        try:
            requests.get(
                DIServises.conf_program().data['downloader'][
                    'check_internet_access_url'
                ],
                timeout=15,
                hooks={'response': self._terminate_check}
            )
            self.s_internet_state.emit(True)
        except DownloadCancel:
            return
        except Exception:
            logging.getLogger('serial-notifier').error(
                'Отстуствует доступ в интернет'
            )
            self.s_internet_state.emit(False)

    def cancel(self):
        self.f_stop = True

    def _terminate_check(self, *args, **kwargs):
        if self.f_stop:
            raise DownloadCancel()


class DownloadCancel(Exception):
    """
    Исключение сообщающие, что загрузку необходимо отметить
    """
    pass


class TimeoutUpdate(Exception):
    """
    Исключение сообщающие, что загрузку необходимо прервать
    """
    pass